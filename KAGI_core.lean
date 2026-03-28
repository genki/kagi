namespace KAGI

abbrev Owner := Nat
abbrev Key   := Nat
abbrev Epoch := Nat

/-- `shared e n` means: there are `n + 1` live shared readers in epoch `e`. -/
inductive LoanState where
  | idle
  | mut (k : Key)
  | shared (e : Epoch) (n : Nat)
deriving DecidableEq, Repr

structure Cell where
  alive : Bool
  loan  : LoanState
deriving DecidableEq, Repr

abbrev Heap := Owner → Cell

def setCell (h : Heap) (o : Owner) (c : Cell) : Heap :=
  fun x => if x = o then c else h x

@[simp] theorem setCell_same (h : Heap) (o : Owner) (c : Cell) :
    setCell h o c o = c := by
  simp [setCell]

@[simp] theorem setCell_other (h : Heap) (o u : Owner) (c : Cell) (hu : u ≠ o) :
    setCell h o c u = h u := by
  simp [setCell, hu]

inductive Action where
  | borrowMut (o : Owner) (k : Key)
  | endMut (o : Owner) (k : Key)
  | borrowShared (o : Owner) (e : Epoch)
  | endShared (o : Owner) (e : Epoch)
  | drop (o : Owner)
deriving DecidableEq, Repr

inductive Step : Heap → Action → Heap → Prop where
  | borrowMut {h o k} :
      (h o).alive = true →
      (h o).loan = LoanState.idle →
      Step h (Action.borrowMut o k)
        (setCell h o { alive := true, loan := LoanState.mut k })

  | endMut {h o k} :
      (h o).loan = LoanState.mut k →
      Step h (Action.endMut o k)
        (setCell h o { alive := (h o).alive, loan := LoanState.idle })

  | borrowSharedIdle {h o e} :
      (h o).alive = true →
      (h o).loan = LoanState.idle →
      Step h (Action.borrowShared o e)
        (setCell h o { alive := true, loan := LoanState.shared e 0 })

  | borrowSharedMore {h o e n} :
      (h o).alive = true →
      (h o).loan = LoanState.shared e n →
      Step h (Action.borrowShared o e)
        (setCell h o { alive := true, loan := LoanState.shared e (Nat.succ n) })

  | endSharedLast {h o e} :
      (h o).loan = LoanState.shared e 0 →
      Step h (Action.endShared o e)
        (setCell h o { alive := (h o).alive, loan := LoanState.idle })

  | endSharedMore {h o e n} :
      (h o).loan = LoanState.shared e (Nat.succ n) →
      Step h (Action.endShared o e)
        (setCell h o { alive := (h o).alive, loan := LoanState.shared e n })

  | drop {h o} :
      (h o).alive = true →
      (h o).loan = LoanState.idle →
      Step h (Action.drop o)
        (setCell h o { alive := false, loan := LoanState.idle })

/-- A well-formed heap never contains an outstanding loan for a dead owner. -/
def WellFormed (h : Heap) : Prop :=
  ∀ o,
    match (h o).loan with
    | LoanState.idle        => True
    | LoanState.mut _       => (h o).alive = true
    | LoanState.shared _ _  => (h o).alive = true

 theorem wf_alive_of_mut {h : Heap} {o : Owner} {k : Key}
    (hw : WellFormed h) (hloan : (h o).loan = LoanState.mut k) :
    (h o).alive = true := by
  have hw0 := hw o
  simpa [WellFormed, hloan] using hw0

 theorem wf_alive_of_shared {h : Heap} {o : Owner} {e : Epoch} {n : Nat}
    (hw : WellFormed h) (hloan : (h o).loan = LoanState.shared e n) :
    (h o).alive = true := by
  have hw0 := hw o
  simpa [WellFormed, hloan] using hw0

/-- One-step preservation of the core safety invariant. -/
theorem step_preserves {h h' : Heap} {a : Action} :
    WellFormed h → Step h a h' → WellFormed h' := by
  intro hw hs u
  cases hs with
  | borrowMut alive idle =>
      by_cases hu : u = o
      · subst u
        simp [WellFormed, setCell]
      · simpa [WellFormed, setCell, hu] using hw u
  | endMut loan =>
      by_cases hu : u = o
      · subst u
        simp [WellFormed, setCell]
      · simpa [WellFormed, setCell, hu] using hw u
  | borrowSharedIdle alive idle =>
      by_cases hu : u = o
      · subst u
        simp [WellFormed, setCell]
      · simpa [WellFormed, setCell, hu] using hw u
  | borrowSharedMore alive shared =>
      by_cases hu : u = o
      · subst u
        simp [WellFormed, setCell]
      · simpa [WellFormed, setCell, hu] using hw u
  | endSharedLast shared =>
      by_cases hu : u = o
      · subst u
        simp [WellFormed, setCell]
      · simpa [WellFormed, setCell, hu] using hw u
  | endSharedMore shared =>
      by_cases hu : u = o
      · subst u
        have halive : (h o).alive = true := wf_alive_of_shared hw shared
        simp [WellFormed, setCell, halive]
      · simpa [WellFormed, setCell, hu] using hw u
  | drop alive idle =>
      by_cases hu : u = o
      · subst u
        simp [WellFormed, setCell]
      · simpa [WellFormed, setCell, hu] using hw u

inductive Reachable : Heap → Heap → Prop where
  | refl (h : Heap) : Reachable h h
  | tail {h1 h2 h3 : Heap} {a : Action} :
      Reachable h1 h2 → Step h2 a h3 → Reachable h1 h3

/-- Safety is preserved for any finite execution prefix. -/
theorem reachable_preserves {h0 h : Heap} :
    WellFormed h0 → Reachable h0 h → WellFormed h := by
  intro hw hr
  induction hr with
  | refl _ =>
      exact hw
  | tail hr hs ih =>
      exact step_preserves ih hs

/-- What downstream crates need to know about one owner.  Key IDs and shared counts are hidden. -/
inductive Exported where
  | idle
  | mut
  | shared (e : Epoch)
deriving DecidableEq, Repr

def export (h : Heap) (o : Owner) : Exported :=
  match (h o).loan with
  | LoanState.idle       => Exported.idle
  | LoanState.mut _      => Exported.mut
  | LoanState.shared e _ => Exported.shared e

/-- If the exported summary says "busy", creating a new mutable borrow is impossible. -/
theorem export_busy_blocks_borrowMut {h h' : Heap} {o : Owner} {k : Key} :
    export h o ≠ Exported.idle →
    ¬ Step h (Action.borrowMut o k) h' := by
  intro hbusy hs
  cases hs with
  | borrowMut alive idle =>
      apply hbusy
      simp [export, idle]

/-- If the exported summary says "busy", dropping is impossible. -/
theorem export_busy_blocks_drop {h h' : Heap} {o : Owner} :
    export h o ≠ Exported.idle →
    ¬ Step h (Action.drop o) h' := by
  intro hbusy hs
  cases hs with
  | drop alive idle =>
      apply hbusy
      simp [export, idle]

/-- If the exported summary says "mut", any shared borrow is impossible. -/
theorem export_mut_blocks_shared {h h' : Heap} {o : Owner} {e : Epoch} :
    export h o = Exported.mut →
    ¬ Step h (Action.borrowShared o e) h' := by
  intro hexp hs
  cases hs with
  | borrowSharedIdle alive idle =>
      simp [export, idle] at hexp
  | borrowSharedMore alive shared =>
      simp [export, shared] at hexp

/-- A shared export for epoch `e1` rules out creating a reader in a different epoch `e2`. -/
theorem export_shared_blocks_foreign_epoch {h h' : Heap} {o : Owner}
    {e1 e2 : Epoch} :
    export h o = Exported.shared e1 →
    e1 ≠ e2 →
    ¬ Step h (Action.borrowShared o e2) h' := by
  intro hexp hne hs
  cases hs with
  | borrowSharedIdle alive idle =>
      simp [export, idle] at hexp
  | borrowSharedMore alive shared =>
      have heq : e2 = e1 := by
        simpa [export, shared] using hexp
      exact hne heq.symm

/-- A shared export is enough to rule out any mutable borrow, even though the summary hides the reader count. -/
theorem export_shared_blocks_borrowMut {h h' : Heap} {o : Owner}
    {e : Epoch} {k : Key} :
    export h o = Exported.shared e →
    ¬ Step h (Action.borrowMut o k) h' := by
  intro hexp hs
  cases hs with
  | borrowMut alive idle =>
      simp [export, idle] at hexp

/-- The compressed export is also sufficient to *extend* sharing in the same epoch.
    Note that the exact reader count remains hidden. -/
theorem export_shared_same_epoch_can_extend {h : Heap} {o : Owner} {e : Epoch} :
    WellFormed h →
    export h o = Exported.shared e →
    ∃ h', Step h (Action.borrowShared o e) h' := by
  intro hw hexp
  cases hloan : (h o).loan with
  | idle =>
      simp [export, hloan] at hexp
  | mut k =>
      simp [export, hloan] at hexp
  | shared e' n =>
      simp [export, hloan] at hexp
      cases hexp
      have halive : (h o).alive = true := wf_alive_of_shared hw hloan
      refine ⟨setCell h o { alive := true, loan := LoanState.shared e (Nat.succ n) }, ?_⟩
      exact Step.borrowSharedMore halive hloan

end KAGI
