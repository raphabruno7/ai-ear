import { NextRequest, NextResponse } from "next/server";

// Protect the dashboard. Cloned from voice-demo: cookie `admin_token` must equal
// ADMIN_SECRET; fail-open when ADMIN_SECRET is unset (local dev).
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (pathname.startsWith("/login") || pathname.startsWith("/api")) {
    return NextResponse.next();
  }

  const secret = process.env.ADMIN_SECRET;
  if (!secret) return NextResponse.next();

  if (req.cookies.get("admin_token")?.value !== secret) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  return NextResponse.next();
}

export const config = {
  // everything except login, api, and Next internals / static assets
  matcher: ["/((?!login|api|_next/static|_next/image|favicon.ico).*)"],
};
