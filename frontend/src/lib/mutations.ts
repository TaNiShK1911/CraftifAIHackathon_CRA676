import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { patchIncident, type Incident, type Status } from "./api";

export function useIncidentStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: Status }) => patchIncident(id, status),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: ["incidents"] });
      const prev = qc.getQueryData<Incident[]>(["incidents"]);
      qc.setQueryData<Incident[]>(["incidents"], (old) => old?.map((i) => (i.id === id ? { ...i, status } : i)));
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(["incidents"], ctx.prev);
      toast.error("Couldn't update incident — backend unreachable");
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["stats"] }),
  });
}
