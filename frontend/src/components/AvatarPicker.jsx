import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Upload, Link as LinkIcon, ImageIcon } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

/**
 * Avatar picker — opens a dialog with two tabs: upload from device or paste a URL.
 * onSaved(newPictureDataOrUrl) is called after successful change.
 */
export default function AvatarPicker({ open, onOpenChange, onSaved, currentUrl }) {
  const [url, setUrl] = useState(currentUrl || "");
  const [uploading, setUploading] = useState(false);
  const [savingUrl, setSavingUrl] = useState(false);

  const handleFile = async (file) => {
    if (!file) return;
    if (file.size > 1_500_000) { toast.error("Imagem demasiado grande (máx 1.5 MB)"); return; }
    if (!file.type?.startsWith("image/")) { toast.error("Apenas imagens"); return; }
    const fd = new FormData();
    fd.append("file", file);
    setUploading(true);
    try {
      const { data } = await api.post("/users/me/avatar", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Foto atualizada");
      onSaved(data.picture);
      onOpenChange(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Falha ao carregar imagem");
    } finally {
      setUploading(false);
    }
  };

  const saveUrl = async () => {
    if (!url || !/^https?:\/\//i.test(url)) {
      toast.error("URL inválido (deve começar por http/https)");
      return;
    }
    setSavingUrl(true);
    try {
      await api.patch("/users/me", { picture: url });
      toast.success("Foto atualizada");
      onSaved(url);
      onOpenChange(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Erro");
    } finally {
      setSavingUrl(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-sm max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading uppercase tracking-tight flex items-center gap-2"><ImageIcon size={18}/> Alterar foto</DialogTitle>
        </DialogHeader>
        <Tabs defaultValue="upload" className="w-full">
          <TabsList className="grid grid-cols-2 rounded-sm">
            <TabsTrigger data-testid="avatar-tab-upload" value="upload" className="font-mono uppercase text-xs tracking-wider rounded-sm"><Upload size={14} className="mr-2"/> Dispositivo</TabsTrigger>
            <TabsTrigger data-testid="avatar-tab-url" value="url" className="font-mono uppercase text-xs tracking-wider rounded-sm"><LinkIcon size={14} className="mr-2"/> URL</TabsTrigger>
          </TabsList>
          <TabsContent value="upload" className="space-y-3 mt-4">
            <Label data-testid="avatar-file-label" htmlFor="avatar-file" className="block cursor-pointer border-2 border-dashed border-border hover:border-primary transition-colors rounded-sm p-8 text-center">
              <Upload size={28} className="mx-auto text-primary mb-2" />
              <div className="font-mono text-sm uppercase tracking-wider">Selecionar imagem</div>
              <div className="font-mono text-[10px] text-muted-foreground tracking-wider mt-1">JPG/PNG/WEBP/GIF · máx 1.5 MB</div>
            </Label>
            <input
              id="avatar-file"
              data-testid="avatar-file-input"
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0])}
              disabled={uploading}
            />
            {uploading && <div className="text-center font-mono text-xs uppercase tracking-wider text-primary">A carregar…</div>}
          </TabsContent>
          <TabsContent value="url" className="space-y-3 mt-4">
            <div className="space-y-1.5">
              <Label className="font-mono uppercase text-[11px] tracking-wider">URL da imagem</Label>
              <Input data-testid="avatar-url-input" placeholder="https://..." value={url} onChange={(e) => setUrl(e.target.value)} className="rounded-sm" />
            </div>
            {url && (
              <div className="flex justify-center">
                <img src={url} alt="preview" className="max-h-32 rounded-sm border border-border" onError={(e) => { e.target.style.display = "none"; }} />
              </div>
            )}
            <Button data-testid="avatar-url-save" disabled={savingUrl || !url} onClick={saveUrl} className="w-full rounded-sm font-mono uppercase tracking-wider">
              {savingUrl ? "A guardar…" : "Usar este URL"}
            </Button>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
