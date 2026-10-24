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
- crea la voce nel menu applicazioni e l'icona.

Opzioni: `--check` (solo verifica), `--yes` (senza domande), `--gpu` (compila anche whisper.cpp per GPU).

L'app controlla da sola, all'avvio, che `pywhispercpp` e `ydotool` ci siano e, se mancano,
chiede di installarli.

## Avvio

Dal menu applicazioni ("VocalWisper") oppure `./run.sh` (con `--minimized` parte nel tray).
Parte una sola istanza: un secondo avvio esce subito.

## Uso

- **Ctrl+Alt+M** (configurabile): avvia/ferma la dettatura. Su KDE la scorciatoia globale è registrata
  automaticamente (anche su Wayland).
- Il **popup** compare in basso al centro della finestra che ha il cursore della tastiera e la segue
  se cambi finestra: microfono = pausa/riprendi, quadratino = ferma, onda = livello della voce.
  Quando non parli va in pausa da solo (giallo).
- Il testo viene scritto nel campo attivo a frasi (dopo una breve pausa o ogni ~4 s di parlato continuo).
- **Ducking**: all'inizio legge il volume attuale, lo porta al livello scelto in *Volume durante la dettatura*
  e alla fine (stop, pausa manuale, chiusura, anche dopo un crash) lo rimette com'era.
- Icona nel tray: bianca = ferma, rossa = in registrazione.
- Impostazioni (modello, lingua, backend, scorciatoia, ducking, autostart) salvate in
  `~/.config/vocalwisper/config.json`, anche se chiudi senza premere Save.
- Modelli scaricati in `~/.local/share/vocalwisper/models`.

## GPU

`pywhispercpp` da pip è solo CPU. Per usare la GPU compila whisper.cpp:

```bash
./build.sh auto      # rileva CUDA / Vulkan / ROCm / CPU
./build.sh cuda      # NVIDIA
./build.sh vulkan    # AMD (e NVIDIA)
./build.sh rocm      # AMD ROCm
./build.sh cpu
```

## Wayland / KDE: note tecniche

- Digitazione: `ydotool` (testo ASCII digitato, testo con accenti incollato via clipboard con
  Shift+Insert, clipboard precedente ripristinata). Serve il servizio utente `ydotool`
  (`systemctl --user enable --now ydotool`, già fatto da `install.sh`).
- Posizione del popup e seguire la finestra attiva: script KWin caricato all'avvio (via DBus).
- Alternativa alla scorciatoia interna: comando `./toggle.sh` assegnabile da
  *Impostazioni di sistema → Scorciatoie*.

## Struttura

`main.py` (orchestrazione) · `vocalwisper/` (audio, trascrizione, overlay, tray, ducking, hotkey,
injector, window/KWin, impostazioni, deps) · `install.sh` · `run.sh` · `build.sh` · `toggle.sh` ·
`requirements.txt`
