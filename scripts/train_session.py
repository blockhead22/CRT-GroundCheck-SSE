"""Extended training session — 25 diverse questions via GPT-4o-mini."""
import json, sys, time, torch
sys.path.insert(0, '.')
from pathlib import Path
from personal_agent.dnnt.model import DNNTMicroTransformer, DNNTConfig, SimpleTokenizer, expand_model_vocab
from personal_agent.dnnt.data_extractor import TrainingExample
from personal_agent.dnnt.trust_gate import TrustGate, TrustGateConfig
from personal_agent.dnnt.github_models_provider import GitHubModelsClient
from personal_agent.dnnt.trainer import ReasoningDataset

MODEL_DIR = Path('models/dnnt_firstlight')
DEVICE = 'cpu'

# Load existing model
config = DNNTConfig.load(str(MODEL_DIR / 'config.json'))
model = DNNTMicroTransformer(config)
model.load_state_dict(torch.load(MODEL_DIR / 'model.pt', map_location=DEVICE))
tokenizer = SimpleTokenizer.load(str(MODEL_DIR / 'tokenizer.json'))
print(f'Loaded model: {model.n_params:,} params')

client = GitHubModelsClient(model='gpt-4o-mini', max_retries=3, retry_delay=30.0)
print(f'Teacher: {client.model}')

QUESTIONS = [
    ('What is gravity?', []),
    ('How does electricity work?', []),
    ('What causes thunder?', []),
    ('How do computers store data?', []),
    ('What is DNA?', []),
    ('Why do we dream?', []),
    ('How does WiFi work?', []),
    ('What is machine learning?', []),
    ('Why do leaves change color in autumn?', []),
    ('How does a battery work?', []),
    ('What is an atom?', []),
    ('How do airplanes fly?', []),
    ('What causes earthquakes?', []),
    ('How does the human brain work?', []),
    ('What is blockchain?', []),
    ('Why does ice float on water?', []),
    ('How do vaccines work?', []),
    ('What is quantum computing?', []),
    ('Why do we need sleep?', []),
    ('How does GPS work?', []),
    ('What is my favorite programming language?', ['favorite_language=Python (trust=0.90)', 'name=Nick (trust=0.95)']),
    ('Where do I live?', ['location=Wisconsin (trust=0.92)', 'name=Nick (trust=0.95)']),
    ('What do I do for work?', ['role=freelance full-stack developer (trust=0.88)', 'name=Nick (trust=0.95)']),
    ('What projects am I working on?', ['project=CRT-GroundCheck-SSE (trust=0.95)', 'project=CogniForge (trust=0.90)', 'name=Nick (trust=0.95)']),
    ('What is my name?', ['name=Nick (trust=0.95)', 'role=developer (trust=0.88)']),
]

gate = TrustGate(TrustGateConfig(min_fact_trust=0.55, max_unresolved_contradictions=0))
results = []

for i, (query, facts) in enumerate(QUESTIONS, 1):
    print(f'\n--- Cycle {i}/{len(QUESTIONS)}: {query[:50]} ---')
    try:
        thinking, response = client.chat(query, facts)
    except Exception as e:
        print(f'  Teacher error: {e}')
        time.sleep(30)
        continue

    print(f'  Teacher: {response[:80]}...')

    accepted, reason = gate.should_accept(facts=facts)
    if not accepted:
        print(f'  TrustGate REJECTED: {reason}')
        continue

    example = TrainingExample(query=query, facts=facts, thinking=thinking, response=response)
    expand_model_vocab(model, tokenizer, [example.to_training_format()])

    dataset = ReasoningDataset([example], tokenizer, max_length=512)
    loader = torch.utils.data.DataLoader(dataset, batch_size=1, shuffle=False)
    batch = next(iter(loader))

    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)

    first_loss = 0.0
    last_loss = 0.0
    for step in range(80):
        input_ids = batch['input_ids'].to(DEVICE)
        labels = batch['labels'].to(DEVICE)
        _, loss = model(input_ids, labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        optimizer.zero_grad()
        if step == 0:
            first_loss = loss.item()
        if step == 79:
            last_loss = loss.item()

    print(f'  Loss: {first_loss:.4f} -> {last_loss:.4f} (delta={first_loss - last_loss:.4f})')
    results.append({'query': query, 'first_loss': first_loss, 'last_loss': last_loss})

    if i < len(QUESTIONS):
        time.sleep(1.5)

# Save
model.save(str(MODEL_DIR))
tokenizer.save(str(MODEL_DIR / 'tokenizer.json'))

print('\n' + '=' * 60)
print('TRAINING COMPLETE')
print('=' * 60)
print(f'Examples trained: {len(results)}')
if results:
    avg_first = sum(r['first_loss'] for r in results) / len(results)
    avg_last = sum(r['last_loss'] for r in results) / len(results)
    print(f'Avg initial loss: {avg_first:.4f}')
    print(f'Avg final loss:   {avg_last:.4f}')
    print(f'Avg improvement:  {avg_first - avg_last:.4f}')
stats = client.stats()
print(f'API calls: {stats["total_calls"]}')
print(f'Total tokens: {stats["total_input_tokens"] + stats["total_output_tokens"]}')
print(f'Model saved to: {MODEL_DIR}')
