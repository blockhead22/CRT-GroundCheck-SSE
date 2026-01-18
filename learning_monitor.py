"""
Continuous Learning Monitor & Auto-Trainer

Monitors active learning progress and automatically retrains when thresholds are met.
"""
import sqlite3
import subprocess
import time
from datetime import datetime

def get_stats():
    """Get current active learning statistics."""
    conn = sqlite3.connect('personal_agent/active_learning.db')
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM gate_events')
    total = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL')
    corrected = c.fetchone()[0]
    
    c.execute('SELECT response_type_actual, COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL GROUP BY response_type_actual')
    dist = dict(c.fetchall())
    
    # Get last training run
    c.execute('SELECT training_examples, validation_accuracy, finished_at FROM training_runs ORDER BY finished_at DESC LIMIT 1')
    last_train = c.fetchone()
    
    conn.close()
    
    return {
        'total': total,
        'corrected': corrected,
        'uncorrected': total - corrected,
        'distribution': dist,
        'last_training': last_train
    }

def should_retrain(stats):
    """Determine if we should retrain based on new data."""
    corrected = stats['corrected']
    last_train = stats['last_training']
    
    # Retrain thresholds
    if corrected >= 300 and (not last_train or last_train[0] < 250):
        return True, "Reached 300 corrections - ML should beat heuristics!"
    
    if corrected >= 200 and (not last_train or last_train[0] < 150):
        return True, "Reached 200 corrections - time to test ML performance"
    
    if last_train and corrected >= last_train[0] + 50:
        return True, f"50 new corrections since last training ({last_train[0]} → {corrected})"
    
    return False, None

def retrain_model():
    """Retrain the ML model."""
    print("\n" + "=" * 70)
    print("🔄 AUTO-RETRAINING ML MODEL")
    print("=" * 70)
    
    result = subprocess.run(
        ['D:\\AI_round2\\.venv\\Scripts\\python.exe', 'train_classifier.py'],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Training complete!")
        # Extract accuracy from output
        for line in result.stdout.split('\n'):
            if 'Test Accuracy:' in line:
                print(f"   {line.strip()}")
    else:
        print("❌ Training failed!")
        print(result.stderr[:500])
    
    return result.returncode == 0

def print_dashboard(stats):
    """Print learning dashboard."""
    print("\n" + "=" * 70)
    print(f"📊 ACTIVE LEARNING DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    print(f"\n📈 Data Collection:")
    print(f"   Total events: {stats['total']}")
    print(f"   Corrected: {stats['corrected']}")
    print(f"   Uncorrected: {stats['uncorrected']}")
    
    print(f"\n🏷️  Label Distribution:")
    for label, count in stats['distribution'].items():
        pct = count / stats['corrected'] * 100 if stats['corrected'] > 0 else 0
        print(f"   {label:15} {count:4} ({pct:5.1f}%)")
    
    print(f"\n🎯 Progress to ML Readiness:")
    corrected = stats['corrected']
    progress = min(corrected / 500 * 100, 100)
    bar_filled = int(progress / 2)
    bar = '█' * bar_filled + '░' * (50 - bar_filled)
    print(f"   [{bar}] {progress:.1f}%")
    print(f"   {corrected}/500 corrections")
    
    if corrected >= 300:
        print(f"\n   🚀 READY FOR ML! You have enough data")
    elif corrected >= 200:
        print(f"\n   ⚡ ALMOST READY! {300 - corrected} more for optimal ML")
    else:
        print(f"\n   📊 COLLECTING DATA... {300 - corrected} more needed")
    
    if stats['last_training']:
        examples, accuracy, finished_at = stats['last_training']
        ts = datetime.fromtimestamp(finished_at).strftime('%Y-%m-%d %H:%M')
        print(f"\n🧠 Last Training:")
        print(f"   Time: {ts}")
        print(f"   Examples: {examples}")
        print(f"   Accuracy: {accuracy:.1%}")
        
        new_data = corrected - examples
        if new_data > 0:
            print(f"   📦 New data: +{new_data} corrections since last training")
    
    print("=" * 70)

def main():
    """Main monitoring loop."""
    print("=" * 70)
    print("🤖 CONTINUOUS LEARNING MONITOR")
    print("=" * 70)
    print("\nMonitoring active learning progress...")
    print("Will auto-retrain when thresholds are met")
    print("Press Ctrl+C to stop\n")
    
    while True:
        try:
            stats = get_stats()
            print_dashboard(stats)
            
            # Check if we should retrain
            should_train, reason = should_retrain(stats)
            if should_train:
                print(f"\n💡 Trigger: {reason}")
                user_input = input("\n🔄 Retrain now? (y/n): ").strip().lower()
                
                if user_input == 'y':
                    if retrain_model():
                        print("\n✅ Retrain successful! Waiting 60s before next check...")
                        time.sleep(60)
                    else:
                        print("\n❌ Retrain failed. Waiting 60s before retry...")
                        time.sleep(60)
                else:
                    print("\nSkipping retrain. Waiting 60s...")
                    time.sleep(60)
            else:
                print(f"\n💤 No retrain needed yet. Checking again in 60s...")
                print(f"   (Will retrain at 200, 300 corrections, or +50 new)")
                time.sleep(60)
                
        except KeyboardInterrupt:
            print("\n\n👋 Stopping monitor...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    # Show current status
    stats = get_stats()
    print_dashboard(stats)
    
    # Check immediate retrain need
    should_train, reason = should_retrain(stats)
    if should_train:
        print(f"\n💡 {reason}")
        print(f"\n🎯 RECOMMENDATION: Run train_classifier.py now!")
    else:
        print(f"\n✅ System up to date")
        print(f"   Collect {max(0, 300 - stats['corrected'])} more corrections for ML readiness")
    
    print(f"\n📝 NEXT STEPS:")
    print(f"   1. Run accelerate_learning.py to collect more data")
    print(f"   2. Run train_classifier.py when ready to retrain")
    print(f"   3. Use this monitor for automated checking")
