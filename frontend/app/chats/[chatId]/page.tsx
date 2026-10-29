import { Suspense } from "react";
import { Workspace } from "@/components/workspace";

export default async function Page({
  params,
}: {
  params: Promise<{ chatId: string }>;
}) {
  const { chatId } = await params;
  return (
    <Suspense>
      <Workspace id={chatId} />
    </Suspense>
  );
}
