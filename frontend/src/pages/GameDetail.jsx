import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import ReviewCard from "@/components/ReviewCard";
import { useAuth } from "@/lib/auth-context";
import { Star, Calendar, Cpu, BookOpen, MessageCircleQuestion, ArrowLeft, Trash2, MoreVertical, Edit2, Heart } from "lucide-react";
import { PLATFORM_LABEL } from "@/lib/game-data";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

const CATEGORY_LABEL = {
  "dica": "Dica",
  "tutorial": "Tutorial",
  "como-zerar": "Como zerar",
  "estrategia": "Estratégia",
  "macete": "Macete",
};

export default function GameDetail() {
  const { gameId } = useParams();
  const { user, refresh } = useAuth();
  const [game, setGame] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [guides, setGuides] = useState([]);

  useEffect(() => {
    api.get(`/games/${gameId}`).then((r) => setGame(r.data));
    api.get(`/games/${gameId}/reviews`).then((r) => setReviews(r.data));
    api.get(`/games/${gameId}/guides`).then((r) => setGuides(r.data));
  }, [gameId]);

  const load = () => {
    api.get(`/games/${gameId}`).then((r) => setGame(r.data));
    api.get(`/games/${gameId}/reviews`).then((r) => setReviews(r.data));
    api.get(`/games/${gameId}/guides`).then((r) => setGuides(r.data));
  };

  if (!game) return <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>;

  const canCreateGuide = user && (user.points >= 50);

  return (
    <div className="space-y-8">
      <Link to="/jogos" className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:text-primary transition-colors">
        <ArrowLeft size={14} /> Voltar ao catálogo
      </Link>

      <div className="grid md:grid-cols-[260px_1fr] gap-8">
        <div className="aspect-[3/4] gs-card overflow-hidden">
          <img src={game.cover} alt={game.title} className="w-full h-full object-cover" />
        </div>
        <div className="space-y-5">
          <div>
            <div className="gs-overline mb-2">{game.developer} · {game.year}</div>
            <h1 className="font-heading font-black text-3xl sm:text-5xl uppercase tracking-tighter leading-tight">{game.title}</h1>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {game.avg_rating != null && (
              <div className="flex items-center gap-2 px-3 py-2 border border-primary/40 bg-primary/10 rounded-sm">
                <Star size={16} className="fill-primary text-primary" />
                <span className="font-mono font-bold text-lg">{game.avg_rating}/10</span>
                <span className="font-mono text-xs text-muted-foreground">({game.review_count} avaliações)</span>
              </div>
            )}
            {game.review_count === 0 && (
              <div className="font-mono text-xs text-muted-foreground tracking-wider uppercase">Ainda sem avaliações</div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {game.genres?.map((g) => (
              <span key={g} className="font-mono text-[11px] uppercase tracking-wider px-2.5 py-1 border border-border rounded-sm">{g}</span>
            ))}
          </div>

          <p className="text-base leading-relaxed text-foreground/90 max-w-2xl">{game.description}</p>

          <div className="flex flex-wrap gap-2">
            <div className="font-mono text-xs uppercase tracking-widest text-muted-foreground mr-2 self-center">Plataformas:</div>
            {game.platforms?.map((p) => (
              <span key={p} className="font-mono text-[11px] uppercase tracking-wider px-2.5 py-1 border border-primary/40 bg-primary/5 text-primary rounded-sm">
                {PLATFORM_LABEL[p] || p}
              </span>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            <Button asChild data-testid="game-review-btn" className="rounded-sm font-mono uppercase tracking-wider"><Link to={`/jogos/${gameId}/avaliar`}>Avaliar este jogo</Link></Button>
            {canCreateGuide && (
              <Button asChild variant="outline" data-testid="game-guide-btn" className="rounded-sm font-mono uppercase tracking-wider"><Link to={`/jogos/${gameId}/guia/novo`}>Criar guia</Link></Button>
            )}
            {user && (
              <Button
                type="button"
                variant="outline"
                data-testid="game-wishlist-toggle"
                onClick={async () => {
                  try {
                    if (user.wishlist?.includes(gameId)) {
                      await api.delete(`/wishlist/${gameId}`);
                      toast.success("Removido da wishlist");
                    } else {
                      await api.post(`/wishlist/${gameId}`);
                      toast.success("Adicionado à wishlist");
                    }
                    refresh();
                  } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
                }}
                className={`rounded-sm font-mono uppercase tracking-wider ${user.wishlist?.includes(gameId) ? "border-primary text-primary" : ""}`}
              >
                <Heart size={14} className={`mr-2 ${user.wishlist?.includes(gameId) ? "fill-current" : ""}`}/> {user.wishlist?.includes(gameId) ? "Na wishlist" : "Wishlist"}
              </Button>
            )}
          </div>
        </div>
      </div>

      <Tabs defaultValue="reviews" className="space-y-6">
        <TabsList className="bg-transparent p-0 border-b border-border rounded-none h-auto gap-6 justify-start">
          <TabsTrigger
            value="reviews"
            data-testid="tab-reviews"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none px-0 py-3 font-mono uppercase tracking-wider text-sm"
          >
            <Star size={14} className="mr-2" /> Avaliações ({reviews.length})
          </TabsTrigger>
          <TabsTrigger
            value="guides"
            data-testid="tab-guides"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none px-0 py-3 font-mono uppercase tracking-wider text-sm"
          >
            <BookOpen size={14} className="mr-2" /> Guias ({guides.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="reviews" className="space-y-4">
          {reviews.length === 0 ? (
            <div className="gs-card p-12 text-center">
              <MessageCircleQuestion size={32} className="mx-auto text-primary mb-3" />
              <div className="font-heading uppercase text-lg tracking-tight">Sê o primeiro a avaliar</div>
              <div className="font-mono text-sm text-muted-foreground mt-2">Partilha a tua opinião e ganha pontos.</div>
            </div>
          ) : (
            reviews.map((r) => <ReviewCard key={r.review_id} review={r} onChanged={load} />)
          )}
        </TabsContent>

        <TabsContent value="guides" className="space-y-4">
          {guides.length === 0 ? (
            <div className="gs-card p-12 text-center">
              <BookOpen size={32} className="mx-auto text-primary mb-3" />
              <div className="font-heading uppercase text-lg tracking-tight">Ainda sem guias</div>
              <div className="font-mono text-sm text-muted-foreground mt-2">
                {canCreateGuide ? "Cria o primeiro guia da comunidade!" : "Atinge o nível Explorador (50 pts) para criar guias."}
              </div>
            </div>
          ) : (
            guides.map((g) => (
              <article key={g.guide_id} data-testid={`guide-${g.guide_id}`} className="gs-card p-5 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-primary">{CATEGORY_LABEL[g.category] || g.category}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">por {g.author_name}</span>
                  </div>
                </div>
                <h3 className="font-heading text-xl font-bold tracking-tight">{g.title}</h3>
                <p className="text-sm leading-relaxed whitespace-pre-line text-foreground/90">{g.content}</p>
              </article>
            ))
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
o"); }
  };

  if (editing) {
    return (
      <article className="gs-card p-5 space-y-3">
        <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
          <SelectTrigger className="rounded-sm w-48"><SelectValue/></SelectTrigger>
          <SelectContent>
            <SelectItem value="dica">Dica</SelectItem>
            <SelectItem value="tutorial">Tutorial</SelectItem>
            <SelectItem value="como-zerar">Como zerar</SelectItem>
            <SelectItem value="estrategia">Estratégia</SelectItem>
            <SelectItem value="macete">Macete</SelectItem>
          </SelectContent>
        </Select>
        <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="rounded-sm font-heading text-lg" />
        <Textarea rows={6} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} className="rounded-sm" />
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={() => setEditing(false)} className="rounded-sm">Cancelar</Button>
          <Button data-testid={`guide-save-${guide.guide_id}`} disabled={saving} onClick={save} className="rounded-sm">Guardar</Button>
        </div>
      </article>
    );
  }

  return (
    <article data-testid={`guide-${guide.guide_id}`} className="gs-card p-5 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-primary">{guide.category}</span>
          <span className="font-mono text-[10px] text-muted-foreground">por {guide.author_name}</span>
        </div>
        {isOwner && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid={`guide-menu-${guide.guide_id}`} className="p-1 rounded-sm hover:bg-muted text-muted-foreground"><MoreVertical size={16}/></button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="rounded-sm">
              <DropdownMenuItem data-testid={`guide-edit-${guide.guide_id}`} onClick={() => setEditing(true)}><Edit2 size={14} className="mr-2"/> Editar</DropdownMenuItem>
              <DropdownMenuItem data-testid={`guide-delete-${guide.guide_id}`} className="text-destructive focus:text-destructive" onClick={() => setConfirm(true)}><Trash2 size={14} className="mr-2"/> Apagar</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      <h3 className="font-heading text-xl font-bold tracking-tight">{guide.title}</h3>
      <p className="text-sm leading-relaxed whitespace-pre-line text-foreground/90">{guide.content}</p>
      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent className="rounded-sm">
          <AlertDialogHeader><AlertDialogTitle>Apagar guia?</AlertDialogTitle><AlertDialogDescription>Esta ação não pode ser revertida.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-sm">Cancelar</AlertDialogCancel>
            <AlertDialogAction data-testid={`guide-delete-confirm-${guide.guide_id}`} className="rounded-sm" onClick={remove}>Apagar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </article>
  );
}
