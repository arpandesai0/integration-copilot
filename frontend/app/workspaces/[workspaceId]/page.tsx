import { Suspense } from "react";
import { Workspace } from "@/components/workspace";
export default async function Page({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  return (
    <Suspense>
      <Workspace key={workspaceId} id={workspaceId} />
    </Suspense>
  );
}
