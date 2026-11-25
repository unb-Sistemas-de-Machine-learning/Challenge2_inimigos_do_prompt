const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function checkApiHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) {
    throw new Error(`API health check failed: ${res.status}`);
  }
  return res.json();
}
