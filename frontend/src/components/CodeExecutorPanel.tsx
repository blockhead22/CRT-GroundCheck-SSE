import React, { useState, useCallback, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { 
  Play, 
  RotateCcw, 
  Sparkles, 
  CheckCircle, 
  XCircle, 
  Clock,
  Code,
  Terminal,
  Loader2,
  Trash2,
  History
} from 'lucide-react';
import { getEffectiveApiBaseUrl } from '../lib/api';

interface ExecutionResult {
  success: boolean;
  stdout: string;
  stderr: string;
  error_type?: string;
  error_message?: string;
  execution_time_ms: number;
  task_id: string;
  code?: string;
  attempt?: number;
}

interface TaskResult {
  task_id: string;
  status: 'running' | 'success' | 'failed';
  description: string;
  attempts: Array<{
    attempt: number;
    code: string;
    result: ExecutionResult;
  }>;
  started_at: string;
  completed_at?: string;
}

interface HistoryItem extends ExecutionResult {
  timestamp: string;
}

// Dynamic API base for external access
const getApiBase = () => getEffectiveApiBaseUrl();

export function CodeExecutorPanel() {
  const [mode, setMode] = useState<'direct' | 'retry' | 'task'>('direct');
  const [code, setCode] = useState('# Write your Python code here\nimport json\n\ndata = {"message": "Hello from CRT!"}\nprint(json.dumps(data, indent=2))');
  const [taskDescription, setTaskDescription] = useState('');
  const [taskContext, setTaskContext] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [maxRetries, setMaxRetries] = useState(3);
  const [timeout, setTimeout] = useState(30);

  // Fetch execution history
  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/code/history?limit=20`);
      const data = await res.json();
      setHistory(data.history || []);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Direct execution
  const executeDirect = async () => {
    setIsExecuting(true);
    setResult(null);
    
    try {
      const res = await fetch(`${getApiBase()}/api/code/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          timeout_seconds: timeout
        })
      });
      
      const data = await res.json();
      setResult(data);
      fetchHistory();
    } catch (err) {
      setResult({
        success: false,
        stdout: '',
        stderr: String(err),
        error_type: 'NetworkError',
        error_message: 'Failed to connect to API',
        execution_time_ms: 0,
        task_id: 'error'
      });
    } finally {
      setIsExecuting(false);
    }
  };

  // Execute with retry
  const executeWithRetry = async () => {
    setIsExecuting(true);
    setResult(null);
    
    try {
      const res = await fetch(`${getApiBase()}/api/code/execute-retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          max_retries: maxRetries,
          timeout_seconds: timeout
        })
      });
      
      const data = await res.json();
      
      // Show final attempt result
      if (data.attempts && data.attempts.length > 0) {
        const lastAttempt = data.attempts[data.attempts.length - 1];
        setResult({
          ...lastAttempt,
          success: data.success,
          stdout: data.final_output || lastAttempt.stdout || '',
          stderr: data.final_error || lastAttempt.stderr || ''
        });
      }
      
      fetchHistory();
    } catch (err) {
      setResult({
        success: false,
        stdout: '',
        stderr: String(err),
        error_type: 'NetworkError',
        error_message: 'Failed to connect to API',
        execution_time_ms: 0,
        task_id: 'error'
      });
    } finally {
      setIsExecuting(false);
    }
  };

  // Run autonomous task
  const runTask = async () => {
    if (!taskDescription.trim()) return;
    
    setIsExecuting(true);
    setTaskResult(null);
    
    try {
      const res = await fetch(`${getApiBase()}/api/code/task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_description: taskDescription,
          context: taskContext || undefined,
          max_retries: maxRetries,
          timeout_seconds: timeout
        })
      });
      
      const data = await res.json();
      setTaskResult(data);
      fetchHistory();
    } catch (err) {
      setTaskResult({
        task_id: 'error',
        status: 'failed',
        description: taskDescription,
        attempts: [],
        started_at: new Date().toISOString()
      });
    } finally {
      setIsExecuting(false);
    }
  };

  // Clear history
  const clearHistory = async () => {
    try {
      await fetch(`${getApiBase()}/api/code/history`, { method: 'DELETE' });
      setHistory([]);
    } catch (err) {
      console.error('Failed to clear history:', err);
    }
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Code Executor
            </CardTitle>
            <CardDescription>
              Write, run, and iterate on Python code
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <input
              type="number"
              value={timeout}
              onChange={(e) => setTimeout(Number(e.target.value))}
              className="w-16 px-2 py-1 text-xs border rounded"
              min={1}
              max={300}
            />
            <span>s timeout</span>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="flex-1 flex flex-col gap-4 overflow-hidden">
        <Tabs value={mode} onValueChange={(v) => setMode(v as typeof mode)} className="flex-1 flex flex-col">
          <TabsList className="grid grid-cols-3">
            <TabsTrigger value="direct" className="flex items-center gap-1">
              <Play className="h-3 w-3" />
              Direct
            </TabsTrigger>
            <TabsTrigger value="retry" className="flex items-center gap-1">
              <RotateCcw className="h-3 w-3" />
              Retry Loop
            </TabsTrigger>
            <TabsTrigger value="task" className="flex items-center gap-1">
              <Sparkles className="h-3 w-3" />
              LLM Task
            </TabsTrigger>
          </TabsList>
          
          {/* Direct Execution */}
          <TabsContent value="direct" className="flex-1 flex flex-col gap-3 mt-3">
            <div className="flex-1 min-h-0">
              <Textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="# Write Python code here..."
                className="h-full font-mono text-sm resize-none"
              />
            </div>
            <Button 
              onClick={executeDirect} 
              disabled={isExecuting || !code.trim()}
              className="w-full"
            >
              {isExecuting ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Running...</>
              ) : (
                <><Play className="h-4 w-4 mr-2" /> Execute</>
              )}
            </Button>
          </TabsContent>
          
          {/* Retry Loop */}
          <TabsContent value="retry" className="flex-1 flex flex-col gap-3 mt-3">
            <div className="flex items-center gap-2 text-sm">
              <span>Max Retries:</span>
              <input
                type="number"
                value={maxRetries}
                onChange={(e) => setMaxRetries(Number(e.target.value))}
                className="w-16 px-2 py-1 border rounded"
                min={1}
                max={10}
              />
            </div>
            <div className="flex-1 min-h-0">
              <Textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="# Code will retry on failure..."
                className="h-full font-mono text-sm resize-none"
              />
            </div>
            <Button 
              onClick={executeWithRetry} 
              disabled={isExecuting || !code.trim()}
              className="w-full"
            >
              {isExecuting ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Running...</>
              ) : (
                <><RotateCcw className="h-4 w-4 mr-2" /> Execute with Retry</>
              )}
            </Button>
          </TabsContent>
          
          {/* LLM Task */}
          <TabsContent value="task" className="flex-1 flex flex-col gap-3 mt-3">
            <div className="flex items-center gap-2 text-sm">
              <span>Max Retries:</span>
              <input
                type="number"
                value={maxRetries}
                onChange={(e) => setMaxRetries(Number(e.target.value))}
                className="w-16 px-2 py-1 border rounded"
                min={1}
                max={10}
              />
            </div>
            <Textarea
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
              placeholder="Describe what you want the LLM to accomplish..."
              className="min-h-[80px] text-sm"
            />
            <Textarea
              value={taskContext}
              onChange={(e) => setTaskContext(e.target.value)}
              placeholder="(Optional) Additional context..."
              className="min-h-[60px] text-sm"
            />
            <Button 
              onClick={runTask} 
              disabled={isExecuting || !taskDescription.trim()}
              className="w-full"
            >
              {isExecuting ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> LLM Working...</>
              ) : (
                <><Sparkles className="h-4 w-4 mr-2" /> Run Task</>
              )}
            </Button>
            
            {/* Task Result */}
            {taskResult && (
              <div className="border rounded-lg p-3 bg-muted/50">
                <div className="flex items-center gap-2 mb-2">
                  {taskResult.status === 'success' ? (
                    <Badge className="bg-green-500"><CheckCircle className="h-3 w-3 mr-1" /> Success</Badge>
                  ) : taskResult.status === 'running' ? (
                    <Badge className="bg-blue-500"><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Running</Badge>
                  ) : (
                    <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" /> Failed</Badge>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {taskResult.attempts.length} attempt(s)
                  </span>
                </div>
                
                {taskResult.attempts.map((attempt, i) => (
                  <details key={i} className="mt-2">
                    <summary className="cursor-pointer text-sm">
                      Attempt {attempt.attempt} - {attempt.result?.success ? '✓' : '✗'}
                    </summary>
                    <pre className="mt-1 p-2 bg-black/80 text-green-400 rounded text-xs overflow-auto max-h-32">
                      {attempt.code}
                    </pre>
                    {attempt.result?.stdout && (
                      <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-auto max-h-24">
                        {attempt.result.stdout}
                      </pre>
                    )}
                  </details>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
        
        {/* Execution Result */}
        {result && mode !== 'task' && (
          <div className="border rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-muted/50">
              <div className="flex items-center gap-2">
                {result.success ? (
                  <Badge className="bg-green-500"><CheckCircle className="h-3 w-3 mr-1" /> Success</Badge>
                ) : (
                  <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" /> Failed</Badge>
                )}
                <span className="text-xs text-muted-foreground">
                  {result.execution_time_ms}ms
                </span>
              </div>
              {result.error_type && (
                <span className="text-xs text-red-500">{result.error_type}</span>
              )}
            </div>
            
            {result.stdout && (
              <div className="border-t">
                <div className="px-3 py-1 text-xs bg-muted/30 border-b">stdout</div>
                <pre className="p-3 text-sm font-mono whitespace-pre-wrap max-h-40 overflow-auto">
                  {result.stdout}
                </pre>
              </div>
            )}
            
            {result.stderr && (
              <div className="border-t">
                <div className="px-3 py-1 text-xs bg-red-500/10 border-b text-red-500">stderr</div>
                <pre className="p-3 text-sm font-mono whitespace-pre-wrap max-h-40 overflow-auto text-red-400">
                  {result.stderr}
                </pre>
              </div>
            )}
          </div>
        )}
        
        {/* History */}
        <div className="border-t pt-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <History className="h-4 w-4" />
              Recent Executions
            </div>
            {history.length > 0 && (
              <Button 
                variant="ghost" 
                size="sm"
                onClick={clearHistory}
                className="h-6 text-xs"
              >
                <Trash2 className="h-3 w-3 mr-1" />
                Clear
              </Button>
            )}
          </div>
          
          <div className="space-y-1 max-h-32 overflow-auto">
            {history.length === 0 ? (
              <p className="text-xs text-muted-foreground">No executions yet</p>
            ) : (
              history.slice().reverse().slice(0, 5).map((item, i) => (
                <div 
                  key={i}
                  className="flex items-center gap-2 text-xs p-1.5 rounded bg-muted/30 hover:bg-muted/50 cursor-pointer"
                  onClick={() => {
                    if (item.code) setCode(item.code);
                  }}
                >
                  {item.success ? (
                    <CheckCircle className="h-3 w-3 text-green-500 shrink-0" />
                  ) : (
                    <XCircle className="h-3 w-3 text-red-500 shrink-0" />
                  )}
                  <span className="truncate flex-1 font-mono">
                    {item.code?.split('\n')[0]?.substring(0, 40) || item.task_id}
                  </span>
                  <span className="text-muted-foreground shrink-0">
                    {item.execution_time_ms}ms
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default CodeExecutorPanel;
