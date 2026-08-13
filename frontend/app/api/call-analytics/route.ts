import { NextResponse } from 'next/server';

export const revalidate = 0;

const analyticsBackendUrl = process.env.CALL_ANALYTICS_BACKEND_URL ?? 'http://localhost:8765';

export async function GET() {
  try {
    const url = new URL('/api/call-analytics', analyticsBackendUrl);
    url.searchParams.set('t', Date.now().toString());

    const res = await fetch(url, {
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' },
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: 'Call Analytics backend returned an error.', status: res.status },
        { status: 502 }
      );
    }

    const data = await res.json();
    return NextResponse.json(data, {
      headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0' },
    });
  } catch (error) {
    console.error('Call Analytics backend is unavailable:', error);
    return NextResponse.json(
      {
        error: 'Call Analytics is unavailable. Start the backend dashboard service on port 8765.',
      },
      { status: 503 }
    );
  }
}
