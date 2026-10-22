
import { useCallback, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  addEdge,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';

import type { Connection, Edge, Node } from '@xyflow/react';

import '@xyflow/react/dist/style.css';
import './App.css';
type WorkflowRunResult = {
  run_id: string | null;
  status: 'success' | 'failed';
  node_results: Record<string, {
    status: string;
    inputs?: Record<string, unknown>;
    outputs?: Record<string, unknown>;
    error?: string;
  }>;
  final_output: unknown;
  error?: string;
};

// 工作流的初始节点。
// position 是节点在画布中的坐标，不是浏览器页面坐标。
const initialNodes = [
  {
    id: 'node_1',
    type: 'input',
    position: { x: 80, y: 150 },
    data: {
      label: 'Text Input',
      nodeType: 'text_input',
      text: 'Hello AI',
    },
  },
  {
    id: 'node_2',
    type: 'default',
    position: { x: 350, y: 150 },
    data: {
      label: 'Text Uppercase',
      nodeType: 'text_uppercase',
    },
  },
  {
    id: 'node_3',
    type: 'output',
    position: { x: 620, y: 150 },
    data: {
      label: 'Output',
      nodeType: 'output',
    },
  },
];

// 初始连线，source 表示上游节点，target 表示下游节点。
const initialEdges: Edge[] = [
  {
    id: 'edge_1',
    source: 'node_1',
    target: 'node_2',
    animated: true,
  },
  {
    id: 'edge_2',
    source: 'node_2',
    target: 'node_3',
    animated: true,
  },
];

function App() {
  const [nodes, setNodes, onNodesChange] =
    useNodesState(initialNodes);

  const [edges, setEdges, onEdgesChange] =
    useEdgesState(initialEdges);

  const [message, setMessage] = useState('');
  const [runResult, setRunResult] = useState<WorkflowRunResult | null>(null);

  const [isRunning, setIsRunning] = useState(false);
  async function runWorkflowOnServer() {
    setIsRunning(true);
    setRunResult(null);

    const workflowPayload = {
      schemaVersion: 1,
      id: 'workflow_demo',
      name: 'Text Uppercase Workflow',
      nodes: nodes.map((node) => ({
        id: node.id,
        type: String(node.data.nodeType ?? node.type),
        position: node.position,
        data: node.data,
      })),
      edges: edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle ?? null,
        targetHandle: edge.targetHandle ?? null,
      })),
    };

    try {
      const response = await fetch(
        'http://127.0.0.1:8000/api/workflows/run',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(workflowPayload),
        },
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail
            ? JSON.stringify(result.detail)
            : `请求失败：HTTP ${response.status}`,
        );
      }

      setRunResult(result);
    } catch (error) {
      setRunResult({
        run_id: null,
        status: 'failed',
        node_results: {},
        final_output: null,
        error: error instanceof Error
          ? error.message
          : '工作流执行失败',
      });
    } finally {
      setIsRunning(false);
    }
  }

  // 当用户把一个节点的输出连接到另一个节点时，
  // React Flow 会提供连接信息，我们将其保存到 edges。
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((currentEdges) =>
        addEdge(connection, currentEdges),
      );
    },
    [setEdges],
  );

  // 添加一个新节点。
  const addTextNode = useCallback(() => {
    const id = `node_${crypto.randomUUID()}`;

    const newNode: Node = {
      id,
      type: 'default',
      position: {
        x: 180 + Math.random() * 240,
        y: 300 + Math.random() * 120,
      },
      data: {
        label: `New Node ${nodes.length + 1}`,
      },
    };

    setNodes((currentNodes) => [
      ...currentNodes,
      newNode,
    ]);

    setMessage('已添加新节点');
  }, [nodes.length, setNodes]);
  // 将当前画布提交给 Python 后端进行校验。
  const validateWorkflowOnServer = useCallback(async () => {
    const workflowPayload = {
      schemaVersion: 1,
      id: 'workflow_demo',
      name: 'Text Uppercase Workflow',
      nodes: nodes.map((node) => ({
        id: node.id,
        type: String(node.data.nodeType ?? node.type),
        position: node.position,
        data: node.data,
      })),
      edges: edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle ?? null,
        targetHandle: edge.targetHandle ?? null,
      })),
    };

    try {
      setMessage('正在请求后端校验...');

      const response = await fetch(
        'http://127.0.0.1:8000/api/workflows/validate',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(workflowPayload),
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      if (result.valid) {
        setMessage(
          `校验通过：${result.node_count} 个节点，` +
          `${result.edge_count} 条连线`,
        );
      } else {
        const errors = Array.isArray(result.errors)
          ? result.errors
              .map((item: unknown) =>
                typeof item === 'string'
                  ? item
                  : JSON.stringify(item),
              )
              .join('；')
          : '未知校验错误';

        setMessage(`校验失败：${errors}`);
      }
    } catch (error) {
      console.error('工作流校验失败', error);

      setMessage(
        '无法连接后端，请检查 FastAPI 是否正在运行',
      );
    }
  }, [nodes, edges]);
  // 将画布数据转换为我们自己的工作流 JSON。
  // 不直接把 React Flow 的内部状态当成后端协议。
  const exportWorkflow = useCallback(() => {
    const workflowPayload = {
      schemaVersion: 1,
      id: 'workflow_demo',
      name: 'Text Uppercase Workflow',
      nodes: nodes.map((node) => ({
        id: node.id,
        type: String(node.data.nodeType ?? node.type),
        position: node.position,
        data: node.data,
      })),

      edges: edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        sourceHandle: edge.sourceHandle ?? null,
        target: edge.target,
        targetHandle: edge.targetHandle ?? null,
      })),
    };

    // 浏览器生成 JSON 文件，用户可以保存到本地。
    const json = JSON.stringify(workflowPayload, null, 2);
    const blob = new Blob([json], {
      type: 'application/json',
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = 'workflow.json';
    link.click();

    URL.revokeObjectURL(url);
    setMessage('工作流 JSON 已导出');
  }, [nodes, edges]);

  return (
    <main className="app">
      <header className="topbar">
        <div>
          <h1>FlowForge AI</h1>
          <p>Visual AI Workflow Builder</p>
        </div>

        <div className="toolbar">
          <button onClick={addTextNode}>
            + 添加节点
          </button>
          <button onClick={validateWorkflowOnServer}>
            后端校验
          </button>
          <button
            type="button"
            onClick={runWorkflowOnServer}
            disabled={isRunning}
          >
            {isRunning ? '运行中...' : '运行工作流'}
          </button>
          <button
            className="primary"
            onClick={exportWorkflow}
          >
            导出工作流 JSON
          </button>
        </div>
      </header>

      <section className="workspace">
        <aside className="sidebar">
          <h3>节点面板</h3>

          <div className="node-item">
            <strong>Text Input</strong>
            <span>输入文本</span>
          </div>

          <div className="node-item">
            <strong>Text Uppercase</strong>
            <span>文本转换</span>
          </div>

          <div className="node-item">
            <strong>Output</strong>
            <span>输出结果</span>
          </div>

          <p className="hint">
            当前版本支持画布内添加节点，
            并通过节点两侧的连接点创建连线。
          </p>
        </aside>

        <div className="canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
            deleteKeyCode={['Backspace', 'Delete']}
          >
            <Background gap={20} size={1} />
            <MiniMap />
            <Controls />

            <Panel position="top-right">
              <div className="status">
                节点：{nodes.length}
                {' | '}
                连线：{edges.length}
              </div>
            </Panel>
          </ReactFlow>
        </div>
      </section>
      {runResult && (
        <section className="run-result">
          <h3>
            工作流状态：
            {runResult.status === 'success' ? '执行成功' : '执行失败'}
          </h3>

          {runResult.status === 'success' ? (
            <p>
              最终输出：
              <strong>{String(runResult.final_output ?? '')}</strong>
            </p>
          ) : (
            <p role="alert">
              错误：{runResult.error ?? '请检查节点执行结果'}
            </p>
          )}

          <details>
            <summary>查看完整执行记录</summary>
            <pre>
              {JSON.stringify(runResult, null, 2)}
            </pre>
          </details>
        </section>
      )}

      <footer className="footer">
        {message || '就绪：可以编辑工作流'}
      </footer>
    </main>
  );
}

export default App;
