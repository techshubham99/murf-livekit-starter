import { NextResponse } from 'next/server';
import { execSync } from 'child_process';
import path from 'path';

export const revalidate = 0;

export async function GET() {
  const ts = Date.now();
  try {
    const res = await fetch(`http://localhost:8765/api/escalations?t=${ts}`, {
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' },
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data, {
        headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0' },
      });
    }
  } catch (error) {
    // Fallback to direct Python database query if port 8765 is not running
  }

  try {
    const backendDir = path.resolve(process.cwd(), '..', 'backend');
    const stdout = execSync('uv run python src/query_escalations.py', {
      cwd: backendDir,
      encoding: 'utf-8',
    });
    const data = JSON.parse(stdout);
    return NextResponse.json(data, {
      headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0' },
    });
  } catch (err: any) {
    return NextResponse.json(
      { requests: [], escalations: [], error: String(err) },
      { status: 500 }
    );
  }
}
