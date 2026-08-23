export function consoleActiveMenu(path: string): string {
  if (path.startsWith('/workbench')) return '/workbench'
  if (path.startsWith('/admin/')) return path.split('/').slice(0, 3).join('/')
  return path
}
