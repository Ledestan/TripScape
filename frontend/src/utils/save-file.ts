/**
 * 行旅识景 TripScape / src/utils/save-file
 * 创建日期: 2026-11-26
 *
 * 导出文件的保存入口，完成:
 *     1. 优先用 File System Access API（showSaveFilePicker）让用户自己选目录与文件名
 *     2. 浏览器不支持或用户取消时：取消不报错，不支持则回落到默认下载
 *
 * 依赖:
 *     依赖库: 无
 *
 * 用法:
 *     const result = await saveBlob(blob, "tripscape-collage-1700000000.png");
 *     if (result === "saved") toast.success("已保存");
 *
 * 注意:
 *     1. 必须在用户手势（点击）的调用栈里触发选择器，否则浏览器会以安全原因拒绝。
 *     2. 用户取消会抛 AbortError，这里吞掉并返回 "cancelled"，不要弹错误。
 */

export type SaveResult = "saved" | "cancelled";

interface SaveFilePickerOptions {
  suggestedName?: string;
  types?: { description: string; accept: Record<string, string[]> }[];
}

type SaveFilePicker = (options: SaveFilePickerOptions) => Promise<{
  createWritable: () => Promise<{
    write: (data: Blob) => Promise<void>;
    close: () => Promise<void>;
  }>;
}>;

/** 取浏览器里的保存选择器（不支持时返回 null） */
function getPicker(): SaveFilePicker | null {
  const win = window as unknown as { showSaveFilePicker?: SaveFilePicker };
  return typeof win.showSaveFilePicker === "function" ? win.showSaveFilePicker : null;
}

/** 回落方案：走浏览器下载（用户可在下载设置里选位置） */
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/**
 * 保存 Blob 到用户选择的位置。
 *
 * 参数：
 *     blob          : Blob，要保存的内容
 *     suggestedName : string，建议文件名
 *     description   : string，选择器里的类型描述
 *
 * 返回：
 *     "saved" | "cancelled"：用户取消时返回 cancelled（不抛错）
 */
export async function saveBlob(
  blob: Blob,
  suggestedName: string,
  description = "PNG 图片"
): Promise<SaveResult> {
  const picker = getPicker();
  if (picker) {
    try {
      const handle = await picker({
        suggestedName,
        types: [{ description, accept: { [blob.type || "image/png"]: [".png"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return "saved";
    } catch (error) {
      if ((error as DOMException)?.name === "AbortError") return "cancelled";
      // 权限被拒或实现差异：退回下载，不让用户看到失败
      downloadBlob(blob, suggestedName);
      return "saved";
    }
  }
  downloadBlob(blob, suggestedName);
  return "saved";
}
