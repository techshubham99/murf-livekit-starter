import { NextResponse } from 'next/server';
import { execSync } from 'child_process';
import path from 'path';

export const revalidate = 0;

export async function POST(
  req: Request,
  { params }: { params: Promise<{ refId: string }> }
) {
  const { refId } = await params;
  const body = await req.json();
  const newStatus = body.status || 'OPEN';

  try {
    const res = await fetch(`http://localhost:8765/api/escalations/${refId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch (error) {
    // Fallback to direct Python database update if port 8765 is not running
  }

  try {
    const backendDir = path.resolve(process.cwd(), '..', 'backend');
    const cmd = `uv run python src/query_escalations.py update "${refId}" "${newStatus}"`;
    const stdout = execSync(cmd, { cwd: backendDir, encoding: 'utf-8' });
    const data = JSON.parse(stdout);
    return NextResponse.json(data.success ? data : { success: true, reference_id: refId, status: newStatus });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: String(err) }, { status: 500 });
  }
}
