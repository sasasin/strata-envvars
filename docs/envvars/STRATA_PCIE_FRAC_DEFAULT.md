# `STRATA_PCIE_FRAC_DEFAULT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

PCIe 経由で GPU が処理する expert miss の割合 (`pcie_frac`) を直接指定する変数ではない。実装が認識する値は `old` と `auto` で、HIP gfx12 の初期 share を旧値へ戻す、または CPU pool の速度から share を更新する機能を有効にする。`old` は PCIe miss 処理そのものを無効にせず、明示的な `--pcie-frac` も上書きしない。CUDA/HIP は `src/program/generate.cpp`、SYCL は `sycl/src/program/generate.cpp` で読み取る。

値はどちらの実装でも文字列全体を `strcmp` で大文字小文字を区別して比較する。空文字、空白付き文字列、`1`、`true` などは `old` / `auto` に一致しない。`std::getenv` の結果を trim や数値変換する処理はない。CUDA/HIP の `old` 判定は `src/program/generate.cpp:5190-5194`、HIP の `auto` 判定は `src/program/generate.cpp:2778-2784`、SYCL の `auto` 判定は `sycl/src/program/generate.cpp:2789-2793`。

## 値と判定

| 実装・条件 | unset | 有効になる値 | 無効・通常扱いの値 |
|---|---|---|---|
| CUDA、`--pcie-frac` 未指定 | `old` ではない。native pack は通常の初期 share と probe を使い、対応する経路では PcieAuto が動く | 完全一致の `old` は PcieAuto を止める。CUDA では gfx12 専用の初期 share 変更はない | `auto`、空文字、`0`、`1`、`true`、`OLD`、` old ` は `old` として扱わない。`auto` 固有の判定もない |
| HIP、`--pcie-frac` 未指定、単一 GPU | gfx1200/gfx1201 の native pack は通常 0.15 から開始し、CPU pool による refinement も既定で許可。他の HIP GPU は native pack 0.55 から開始し refinement しない | `old`: gfx12 の初期 share を 0.55 に戻し、refinement を止める。`auto`: gfx12 以外でも refinement を許可 | `auto` 以外は gfx12 外の refinement を有効にしない。`old` 以外の文字列は初期 share を旧値に戻さない |
| SYCL、native pack かつ PCIe probe 成功、`--pcie-frac` 未指定 | probe で得た値を使い、PcieAuto は無効 | 完全一致の `auto` で PcieAuto を許可（layer split 中は無効） | `old`、空文字、`1`、`AUTO` などは PcieAuto を有効にしない。SYCL にはこの変数による gfx12 の 0.15 初期 share 分岐がない |

HIP gfx12 の 0.15 は `pcie_share_gfx12_default()` が HIP build かつ GPU architecture が gfx12 WMMA 対応の場合に true となり、`pcie_start_frac()` が native pack、`old` でない、`STRATA_DEFAULTS` が 026 でない場合に選ぶ値である。`STRATA_DEFAULTS=026` は `STRATA_DEFAULTS` 自身の読み取り時に一度判定され、`026`、`0.2.6`、`v0.2.6` の完全一致だけが該当する。NVFP4 pack は 0.25、canonical Q2_0 pack は 0.2 が別の初期値で、gfx12 判定による変更を受けない（`src/program/generate.cpp:2736-2744,2765-2771,5190-5194`; `include/strata/core/defaults_026.hpp:21-39`）。

どの実装でも `--pcie-frac` を指定し、その値が内部 sentinel の `-1` 以上なら環境変数による初期値処理に入りません。CLI 値は `std::atof` で読み取られます（CUDA/HIP: `src/program/generate.cpp:3873,4484-4486`; SYCL: `sycl/src/program/generate.cpp:1998,2199,2769-2770`）。

## 有効になる条件

- **`old`** は CUDA/HIP の PCIe share 初期化ブロック内でのみ評価される。`--pcie-frac` が指定済みならそのブロック自体に入らず、変数はその起動の share に作用しない（`src/program/generate.cpp:5187-5194`）。
- **HIP の初期 share** を 0.15 にするのは gfx1200/gfx1201 と native pack の組み合わせだけ。`STRATA_DEFAULTS=026` または `old` なら 0.55。gfx12 以外の HIP GPU、CUDA、SYCL にはこの 0.15 の既定分岐はない（`src/program/generate.cpp:2736-2744,2765-2771`; `include/strata/core/defaults_026.hpp:32-39`）。
- **CUDA の PcieAuto** は probe 成功後の share 初期化で設定される。native pack では通常の GPU 構成で候補になる。canonical pack は CUDA で probe される経路に限られ、Windows ではさらに `STRATA_PCIE_AUTO_CANON=1` が必要。`old` はこの自動更新を止める（`src/program/generate.cpp:5196-5217`）。
- **HIP の PcieAuto** は probe 成功した native pack で、gfx12 なら既定で候補になる。gfx12 以外は `STRATA_PCIE_FRAC_DEFAULT=auto` が必要。layer split では `STRATA_PCIE_AUTO_SPLIT` 等から決まる `pcie_auto_split_ok()` が true の場合だけ候補になり、HIP の split は opt-in（`src/program/generate.cpp:2720-2731,2778-2784,5218-5227`）。
- PcieAuto が作られても、expert がすべて VRAM resident、batch 使用中、peer GPU 使用中（CUDA/HIP）なら実際の更新処理は開始しない。SYCL では all-resident、batch、または複数 stage で更新しない（`src/program/generate.cpp:13815-13818,13867-13875`; `sycl/src/program/generate.cpp:8398-8411`）。miss が少なく測定条件に届かない場合も値は変わらない。
- **SYCL の `auto`** は native pack の probe 成功時にだけ読まれる。layer split では `pcie_frac_auto` が false。さらに xe driver で `--stream-experts` がない場合、未指定 CLI share は後続処理で 0 に上書きされる（`sycl/src/program/generate.cpp:2770-2797,2789-2793,2804-2814`）。

## 実行時の詳細

読み取りは起動時、`--pcie-frac` の未指定を確認した後の初期化中に行われる。`old` 判定はその起動のローカル変数で、HIP の `auto` 判定は同じ初期化経路の helper から取得する。SYCL の `auto` も probe 成功時に一度取得する。これらの値をリクエストごとに再読する処理はなく、実行中に環境を変更しても初期化済みの判定は更新されない（`src/program/generate.cpp:2780-2784,5187-5194,5222-5227`; `sycl/src/program/generate.cpp:2789-2793`）。

PcieAuto が有効な場合、初期 share は probe 帯域で調整された後、decode window ごとに CPU pool の miss 処理時間と PCIe link 帯域から更新される。CUDA/HIP 実装は最初の 48 window、その後 96 window ごとに評価し、miss が 300 件未満なら測定を延期、最大 3 回更新する。2000 window まで測定に足る miss がない場合は自動更新を止める。CPU miss 時間が 1 µs 以下、expert byte 数または link 帯域が正でない場合も新しい share は返さない。新しい値が現行値から 0.025 未満の差なら変更・更新ログを出さない。share の計算は `link / (link + k * CPU rate)` を 0.05 刻みに丸め、最低 0.10、上限は `STRATA_PCIE_SHARE_MAX` 等から得る ceiling に制限する。`STRATA_PCIE_K_RULE` も係数 `k` の規則に関係する（`src/program/generate.cpp:2968-3022,13867-13904`）。

SYCL の PcieAuto も 48 window、その後 96 window ごとに最大 3 回更新し、300 miss 未満では測定を延期する。係数は 1.85、share は 0.10..0.60 に制限される。更新時は `drive.d.pcie_num` も新しい割合から再設定される（`sycl/src/program/generate.cpp:1697-1734,8403-8425,12522-12526`）。

最終的な `pcie_frac` は verifier/drive に渡す PCIe miss 数 (`pcie_num`) に変換され、CPU pool が処理する miss と GPU が PCIe から読む miss の配分を変える。環境変数自体はモデルの出力や share の数値を直接指定しない（`src/program/generate.cpp:13814,13892-13904`; `sycl/src/program/generate.cpp:8397-8398,8422-8425`）。

Strata の設定スイッチ側では「Faster answers on Radeon RX 9000 / AI PRO R9700」は既定 ON で、OFF を run config に反映する値が `STRATA_PCIE_FRAC_DEFAULT=old`。これは環境変数の読み取りを実装する箇所ではなく、エンジンに渡す設定値の由来である（`strata_control/speed_switches.py:47-50`）。

## ログと測定値

- probe 成功時は `strata generate: PCIe probe: ...` の行に帯域と初期 `pcie_frac` を出す。probe 失敗時は `strata generate: PCIe probe failed -> pcie_frac default ...` を出す（CUDA/HIP: `src/program/generate.cpp:5208-5230`; SYCL: `sycl/src/program/generate.cpp:2773-2796`）。
- share が更新された場合、CUDA/HIP は `strata serve: PCIe share: the CPU pool takes ... -> pcie_frac ...`、layer split の stage 更新は `strata serve: PCIe share: stage ...` を stderr に出す。SYCL は `strata serve: PCIe share: ... -> pcie_frac ...` を stderr に出す（`src/program/generate.cpp:13879-13904`; `sycl/src/program/generate.cpp:8412-8425`）。
- SYCL の xe driver かつ `--stream-experts` なしで明示的に正の `--pcie-frac` を指定すると、実装は pageable host memory に関する `WARNING` 行を出す。これは `STRATA_PCIE_FRAC_DEFAULT` の警告ではなく、後続の share 条件の警告である（`sycl/src/program/generate.cpp:2804-2814`）。

## 根拠

- `src/program/generate.cpp:2720-2731,2736-2784,5187-5230` — CUDA/HIP の GPU・値判定、share 初期化、probe、自動更新の有効化。
- `src/program/generate.cpp:2968-3022,13867-13904` — PcieAuto の測定条件、share 更新、ログ。
- `sycl/src/program/generate.cpp:1688-1735,2769-2814,8397-8425,12522-12526` — SYCL の probe、`auto` 判定、xe 条件、更新。
- `include/strata/core/defaults_026.hpp:21-39` — `STRATA_DEFAULTS` の判定と PCIe 初期 share。
- `strata_control/speed_switches.py:47-50` — Radeon 9000 向け設定スイッチが書き込む `old` 値。
