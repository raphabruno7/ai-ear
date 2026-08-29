import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

async function login(formData: FormData) {
  "use server";
  const secret = process.env.ADMIN_SECRET;
  if (secret && formData.get("password") === secret) {
    (await cookies()).set("admin_token", secret, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
    redirect("/");
  }
  redirect("/login?e=1");
}

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { e } = await searchParams;
  return (
    <form action={login} className="mx-auto mt-16 max-w-xs">
      <h1 className="text-lg font-semibold">Sign in</h1>
      <input
        type="password"
        name="password"
        placeholder="Admin secret"
        autoFocus
        className="mt-4 w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
      />
      {e && <p className="mt-2 text-sm text-red-600">Wrong password.</p>}
      <button className="mt-3 w-full rounded bg-zinc-900 px-3 py-2 text-sm text-white dark:bg-zinc-100 dark:text-zinc-900">
        Enter
      </button>
    </form>
  );
}
