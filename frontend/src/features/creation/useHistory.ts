/**
 * 行旅识景 TripScape / src/features/creation/useHistory
 *
 * 画布撤销/重做的小型历史栈，完成:
 *     1. 提交式更新：apply(next) 记一步，replace(next) 不记步（用于拖拽中的实时预览）
 *     2. 撤销/重做：至少 20 步（HISTORY_LIMIT = 30）
 *     3. 重置：换模板、清空画布后从新状态重新计数
 *
 * 依赖:
 *     依赖库: react
 *
 * 用法:
 *     const history = useHistory<ComposeDoc>(initial, docSignature);
 *     history.apply(nextDoc);   // 记一步
 *     history.undo(); history.redo();
 *
 * 注意:
 *     1. 拖拽/缩放的中间态用 replace 写入，松手时 apply 一次，
 *        否则一次拖拽会产生几十步历史。
 *     2. 相同签名不记步：避免"点一下没改"也占一步。
 */

import { useCallback, useMemo, useRef, useState } from "react";

export interface HistoryApi<T> {
  value: T;
  /** 提交一步（会进历史） */
  apply: (next: T) => void;
  /** 只替换当前值（不进历史），用于拖拽中的预览 */
  replace: (next: T) => void;
  /** 重置历史，回到给定值 */
  reset: (next: T) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  /** 历史里已有多少步（用于"至少 20 步"的验收） */
  depth: number;
}

export function useHistory<T>(initial: T, signature: (value: T) => string, limit = 30): HistoryApi<T> {
  const [value, setValue] = useState<T>(initial);
  const past = useRef<T[]>([]);
  const future = useRef<T[]>([]);
  const current = useRef<T>(initial);
  current.current = value;

  const apply = useCallback(
    (next: T) => {
      if (signature(next) === signature(current.current)) {
        setValue(next);
        return;
      }
      past.current = [...past.current, current.current].slice(-limit);
      future.current = [];
      setValue(next);
    },
    [limit, signature]
  );

  const replace = useCallback((next: T) => setValue(next), []);

  const reset = useCallback((next: T) => {
    past.current = [];
    future.current = [];
    setValue(next);
  }, []);

  const undo = useCallback(() => {
    const previous = past.current.pop();
    if (previous === undefined) return;
    future.current = [current.current, ...future.current].slice(0, limit);
    setValue(previous);
  }, [limit]);

  const redo = useCallback(() => {
    const [next, ...rest] = future.current;
    if (next === undefined) return;
    future.current = rest;
    past.current = [...past.current, current.current].slice(-limit);
    setValue(next);
  }, [limit]);

  return useMemo(
    () => ({
      value,
      apply,
      replace,
      reset,
      undo,
      redo,
      canUndo: past.current.length > 0,
      canRedo: future.current.length > 0,
      depth: past.current.length,
    }),
    [value, apply, replace, reset, undo, redo]
  );
}