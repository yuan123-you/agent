export type KbPreview =
  | { kind: 'pdf'; url: string }
  | { kind: 'text'; content: string }

export async function toKbPreview(blob: Blob, fileFormat: string): Promise<KbPreview> {
  return fileFormat.toUpperCase() === 'PDF'
    ? { kind: 'pdf', url: URL.createObjectURL(blob) }
    : { kind: 'text', content: await blob.text() }
}

export function releaseKbPreview(preview: KbPreview | null): void {
  if (preview?.kind === 'pdf') URL.revokeObjectURL(preview.url)
}
