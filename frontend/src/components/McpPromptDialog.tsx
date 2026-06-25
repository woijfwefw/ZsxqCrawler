'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Clipboard, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { apiClient, McpPromptInfo } from '@/lib/api';
import { cn } from '@/lib/utils';

const PROMPT_LINE_HEIGHT = 18;
const PROMPT_OVERSCAN_LINES = 10;
const PROMPT_INITIAL_VIEWPORT_HEIGHT = 360;
const PROMPT_MIN_CHARS_PER_ROW = 24;
const PROMPT_AVERAGE_CHAR_WIDTH = 5.8;

interface McpPromptDialogProps {
  className?: string;
  compact?: boolean;
}

function McpIcon({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn('inline-block h-4 w-4 bg-current', className)}
      style={{
        WebkitMask: 'url("/api/assets/mcp.svg") center / contain no-repeat',
        mask: 'url("/api/assets/mcp.svg") center / contain no-repeat',
      }}
    />
  );
}

interface PromptVisualLine {
  key: string;
  sourceLineNumber: number;
  text: string;
  continuation: boolean;
}

function pickWrapIndex(text: string, limit: number): number {
  if (text.length <= limit) return text.length;

  const lowerBound = Math.max(1, Math.floor(limit * 0.55));
  const separators = [' ', '\\', '/', ',', '，', ';', '；'];
  for (let index = limit; index >= lowerBound; index -= 1) {
    if (separators.includes(text[index])) {
      // 路径分隔符保留在上一行末尾，空格则丢弃，避免下一行开头多空格。
      return text[index] === ' ' ? index : index + 1;
    }
  }

  return limit;
}

function wrapPromptLine(line: string, sourceLineNumber: number, charsPerRow: number): PromptVisualLine[] {
  if (!line) {
    return [{ key: `${sourceLineNumber}:0`, sourceLineNumber, text: ' ', continuation: false }];
  }

  const rows: PromptVisualLine[] = [];
  const indent = line.match(/^\s*/)?.[0] || '';
  const continuationPrefix = `${indent}  `;
  let rest = line;
  let part = 0;

  while (rest.length > charsPerRow) {
    const prefix = part === 0 ? '' : continuationPrefix;
    const limit = Math.max(PROMPT_MIN_CHARS_PER_ROW, charsPerRow - prefix.length);
    const cutIndex = pickWrapIndex(rest, limit);
    const chunk = rest.slice(0, cutIndex).trimEnd();

    rows.push({
      key: `${sourceLineNumber}:${part}`,
      sourceLineNumber,
      text: `${prefix}${chunk}`,
      continuation: part > 0,
    });

    rest = rest.slice(cutIndex);
    if (rest.startsWith(' ')) rest = rest.trimStart();
    part += 1;
  }

  rows.push({
    key: `${sourceLineNumber}:${part}`,
    sourceLineNumber,
    text: `${part === 0 ? '' : continuationPrefix}${rest}`,
    continuation: part > 0,
  });

  return rows;
}

function VirtualPromptViewer({ text }: { text: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(PROMPT_INITIAL_VIEWPORT_HEIGHT);
  const [viewportWidth, setViewportWidth] = useState(720);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const updateSize = () => {
      setViewportHeight(element.clientHeight || PROMPT_INITIAL_VIEWPORT_HEIGHT);
      setViewportWidth(element.clientWidth || 720);
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const charsPerRow = useMemo(() => {
    // 扣除行号栏、左右内边距和滚动条宽度后，按等宽小字体估算每行可容纳字符数。
    const contentWidth = Math.max(160, viewportWidth - 68);
    return Math.max(PROMPT_MIN_CHARS_PER_ROW, Math.floor(contentWidth / PROMPT_AVERAGE_CHAR_WIDTH));
  }, [viewportWidth]);

  const rows = useMemo(() => {
    return text
      .split(/\r?\n/)
      .flatMap((line, index) => wrapPromptLine(line, index + 1, charsPerRow));
  }, [text, charsPerRow]);

  const startIndex = Math.max(0, Math.floor(scrollTop / PROMPT_LINE_HEIGHT) - PROMPT_OVERSCAN_LINES);
  const endIndex = Math.min(
    rows.length,
    Math.ceil((scrollTop + viewportHeight) / PROMPT_LINE_HEIGHT) + PROMPT_OVERSCAN_LINES
  );
  const visibleRows = rows.slice(startIndex, endIndex);

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label="MCP 配置提示词"
      tabIndex={0}
      className="h-[min(48vh,360px)] w-full min-w-0 max-w-full overflow-y-auto overflow-x-hidden rounded-lg border border-border bg-muted/20 font-mono text-[10px]"
      onScroll={(event) => {
        setScrollTop(event.currentTarget.scrollTop);
        setViewportHeight(event.currentTarget.clientHeight || PROMPT_INITIAL_VIEWPORT_HEIGHT);
        setViewportWidth(event.currentTarget.clientWidth || 720);
      }}
    >
      <div
        className="relative w-full min-w-0"
        style={{
          height: Math.max(rows.length, 1) * PROMPT_LINE_HEIGHT,
        }}
      >
        {visibleRows.map((row, index) => {
          const rowIndex = startIndex + index;
          return (
            <div
              key={row.key}
              className="absolute left-0 flex w-full min-w-0 overflow-hidden"
              style={{
                top: rowIndex * PROMPT_LINE_HEIGHT,
                height: PROMPT_LINE_HEIGHT,
                lineHeight: `${PROMPT_LINE_HEIGHT}px`,
              }}
            >
              <span className="w-10 shrink-0 select-none border-r border-border bg-background/95 px-1.5 text-right text-[9px] text-muted-foreground">
                {row.continuation ? '↳' : row.sourceLineNumber}
              </span>
              <code className="block min-w-0 flex-1 overflow-hidden whitespace-pre-wrap break-all px-2 text-foreground">
                {row.text}
              </code>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function McpPromptDialog({ className, compact = false }: McpPromptDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [info, setInfo] = useState<McpPromptInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || info || loading) return;

    const loadPrompt = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getMcpPrompt();
        setInfo(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : '加载 MCP 提示词失败';
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    void loadPrompt();
  }, [open, info, loading]);

  const handleCopy = async () => {
    if (!info?.prompt) return;

    try {
      await navigator.clipboard.writeText(info.prompt);
      setCopied(true);
      toast.success('MCP 配置提示词已复制');
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.error('复制失败，请手动选择文本复制');
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size={compact ? 'icon' : 'default'}
          className={cn('flex items-center gap-2', className)}
          title="配置 MCP 数据分析"
        >
          <McpIcon />
          {!compact && <span>MCP</span>}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-[calc(100vw-2rem)] overflow-hidden sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <McpIcon className="h-5 w-5" />
            MCP 数据分析接入
          </DialogTitle>
          <DialogDescription>
            复制下面这段提示词给你的 AI，它会帮你把本项目的知识星球数据库接入 MCP 客户端。
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 min-w-0 space-y-3 overflow-hidden">
          {loading && (
            <div className="flex items-center gap-2 rounded-lg border border-border p-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在生成项目专属 MCP 配置提示词...
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {info && (
            <>
              <div className="grid grid-cols-1 gap-2 text-xs md:grid-cols-2">
                <div className="min-w-0 rounded-lg border border-border p-2">
                  <div className="text-muted-foreground">MCP 脚本</div>
                  <div className="mt-1 break-all font-mono">{info.script_path}</div>
                </div>
                <div className="min-w-0 rounded-lg border border-border p-2">
                  <div className="text-muted-foreground">输出数据库示例</div>
                  <div className="mt-1 break-all font-mono">
                    {info.database_path || '自动发现 output/databases'}
                  </div>
                </div>
              </div>
              <div className="min-w-0 space-y-1">
                <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>提示词预览（虚拟列表，自动换行）</span>
                  <span>{info.prompt.split(/\r?\n/).length} 原始行</span>
                </div>
                <VirtualPromptViewer text={info.prompt} />
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            关闭
          </Button>
          <Button onClick={handleCopy} disabled={!info?.prompt}>
            {copied ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
            {copied ? '已复制' : '复制提示词'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
