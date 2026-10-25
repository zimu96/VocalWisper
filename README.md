# VocalWisper

Dettatura vocale locale, leggera, basata su [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
(CUDA / AMD Vulkan-ROCm / CPU). Pensata per KDE Plasma (Wayland e X11).

## Installazione

```bash
git clone <questo repo> VocalWisper && cd VocalWisper
./install.sh            # controlla cosa manca e lo installa
```

`install.sh` fa tutto da solo:
- controlla i moduli Python (PyQt6, numpy, Pillow, pyaudio, pywhispercpp) e i programmi
  di sistema (`pactl`, `wl-clipboard`, `ydotool` su Wayland) e installa quelli mancanti
  (`pacman` per i pacchetti di sistema, `pip --user` per il resto);
- attiva il servizio utente `ydotool`;
- aggiunge l'utente al gruppo `input` (serve alla scorciatoia globale su Wayland; dopo
  l'aggiunta bisogna uscire e rientrare nella sessione);
- crea la voce nel menu applicazioni e l'icona.

Opzioni: `--check` (solo verifica), `--yes` (senza domande), `--gpu` (compila anche whisper.cpp per GPU).

L'app controlla da sola, all'avvio, che `pywhispercpp` e `ydotool` ci siano e, se mancano,
chiede di installarli.

## Avvio

Dal menu applicazioni ("VocalWisper") oppure `./run.sh` (con `--minimized` parte nel tray).
Parte una sola istanza: un secondo avvio esce subito.

## Uso

- **Ctrl+Alt+M** (configurabile): avvia/ferma la dettatura, da qualsiasi finestra. Su Wayland
  l'app legge direttamente i dispositivi di tastiera (`/dev/input`), quindi non dipende dalle
  scorciatoie di KDE; serve solo che l'utente sia nel gruppo `input` (lo fa `install.sh`).
  Se non può leggere `/dev/input`, usa le scorciatoie KDE e infine `pynput` su X11.
- Il **popup** compare in basso al centro della finestra in cui avvii la dettatura e **resta lì**; anche
  il **testo viene scritto sempre in quella finestra**, anche se clicchi altrove o la finestra non è in
  primo piano (l'app le dà il focus per un attimo, scrive e lo ridà alla finestra che stavi usando).
  Se la finestra viene chiusa, scrive dove c'è il cursore. Per cambiare finestra ferma la dettatura
  (stop, non pausa) e riavviala. Nelle impostazioni si può scegliere che popup e scrittura seguano
  invece la finestra attiva.
  Microfono = pausa/riprendi, quadratino = ferma, onda = livello della voce.
  Quando non parli va in pausa da solo (circa 0,3 s di silenzio).
- Il testo viene scritto nel campo attivo a frasi (dopo ~0,5 s di pausa o ogni ~6 s di parlato continuo).
  La trascrizione gira in un thread separato: ascolto e indicatore di pausa non si bloccano mai.
- **Microfono**: mentre detti, l'app regola da sola il volume del microfono (lo alza se la voce è
  troppo debole, lo abbassa se satura) e a fine dettatura rimette il livello di prima, quindi chiamate
- **Ducking**: all'inizio legge il volume attuale, lo porta al livello scelto in *Volume durante la dettatura*
  e alla fine (stop, pausa manuale, chiusura, anche dopo un crash) lo rimette com'era.
- Icona nel tray: bianca = ferma, rossa = in registrazione.
- Impostazioni (modello, lingua, backend, scorciatoia, ducking, autostart) salvate in
  `~/.config/vocalwisper/config.json`, anche se chiudi senza premere Save.
- Modelli scaricati in `~/.local/share/vocalwisper/models`.

## Qualità e velocità

- Con una GPU NVIDIA usa **`large-v3-turbo`** (1,6 GB, scaricato al primo uso): è il più preciso in
  italiano e su RTX 5060 Ti trascrive 4 s di voce in ~0,1 s. Senza GPU usa `small` (o `base` se il
  computer è lento). `tiny` è velocissimo ma sbaglia spesso. Modelli: tiny, base, small, medium, large-v3-turbo.
- Prima di trascrivere, silenzi e rumore vengono scartati (soglia adattiva al rumore di fondo);
  frasi ripetute all'infinito, riempitivi isolati ("eh", "mm") e le allucinazioni tipiche di whisper
  ("Grazie." sul rumore) vengono filtrati.
- Per attivare la GPU serve compilare whisper.cpp (vedi sotto): `pywhispercpp` da pip è solo CPU.

## GPU

```bash
./build.sh auto      # rileva CUDA / Vulkan / ROCm / CPU (NVIDIA: CUDA, ~10 minuti)
./build.sh cuda      # NVIDIA (serve il toolkit CUDA in /opt/cuda)
./build.sh vulkan    # AMD (e NVIDIA)
./build.sh rocm      # AMD ROCm
./build.sh cpu
```

## Wayland / KDE: note tecniche

- Scorciatoia globale: le scorciatoie di KDE (`kglobalaccel`) possono non funzionare quando
  KWin e la libreria `kglobalaccel` hanno versioni diverse (nei log di KWin compare
  `Could not find slot KGlobalAccelD::doRegister`). Per questo l'app legge i tasti
  direttamente da `/dev/input/event*`: funziona sempre, anche su Wayland, e richiede solo
  il gruppo `input`.
- Digitazione: `ydotool` (testo ASCII digitato, testo con accenti incollato via clipboard con
  Shift+Insert, clipboard precedente ripristinata). Serve il servizio utente `ydotool`
  (`systemctl --user enable --now ydotool`, già fatto da `install.sh`).
- Posizione del popup e seguire la finestra attiva: script KWin caricato all'avvio (via DBus).
- I tasti vengono letti solo per riconoscere la combinazione scelta: il testo digitato non viene
  registrato né salvato.
- Alternativa alla scorciatoia interna: comando `./toggle.sh` assegnabile da
  *Impostazioni di sistema → Scorciatoie* (utile se `/dev/input` non è leggibile).

## Struttura

`main.py` (orchestrazione) · `vocalwisper/` (audio, trascrizione e pulizia del testo, overlay, tray,
ducking, hotkey KDE e `/dev/input`, injector, window/KWin, impostazioni, deps) · `install.sh` ·
`run.sh` · `build.sh` · `toggle.sh` · `requirements.txt`
