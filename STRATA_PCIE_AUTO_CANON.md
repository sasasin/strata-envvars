# `STRATA_PCIE_AUTO_CANON`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

canonical Q2_0 pack（native pack ではない pack）の PCIe share を、起動時に link を probe して PcieAuto で refine するかを決めます。Windows CUDA ビルドでのみ環境から値を読みます。Linux CUDA ではこの変数は read されず、canonical pack は既定で probe されます（`STRATA_PCIE_FRAC_DEFAULT=old` でのみ opt-out）。HIP では read されず、canonical pack の PcieAuto は CUDA 限定なので probe されません。

Windows CUDA の既定は opt-in（OFF）です。RTX 5070 で code +2.5%、short answer -3.3%（`docs/DETAILS.md:1653`）だったため、Windows では `=1` のときだけ probe・refine が有効になります。

判定結果は起動時のこの block で一度 read されます（static cache ではなく、block が一度だけ走る）。

## 値と判定

Windows CUDA 分岐（`src/program/generate.cpp:2741-2744`）だけがこの名前を `std::getenv` で読み、先頭文字 `pac[0] == '1'` を調べます。結果は `pf_old_canon` に入ります。

| ビルド | 入力 | `pf_old_canon` | canonical pack の probe |
|---|---|---|---|
| Windows CUDA | 未設定 | true | しない（既定） |
| Windows CUDA | 空文字 | true | しない |
| Windows CUDA | `0`, `true`, `false` | true | しない |
| Windows CUDA | `1`, `10`, `1anything` | `pf_old` | `pf_old` が false なら probe |
| Windows CUDA | `=1` かつ `STRATA_PCIE_FRAC_DEFAULT=old` | true | しない |
| Linux CUDA | （read されない） | `pf_old` | `pf_old` が false なら probe |
| HIP | （read されない） | true | しない |

`pf_old` は `STRATA_PCIE_FRAC_DEFAULT` の文字列全体が `old` と一致したとき true（`strcmp`、`src/program/generate.cpp:2739-2740`）。`STRATA_PCIE_AUTO_CANON` は先頭文字比較で、大文字小文字・数値妥当性は検査しません。

## 有効になる条件

- `--pcie-frac` が明示されていないこと。`o.pcie_frac` の既定は -1（`src/program/generate.cpp:575`）で、`o.pcie_frac < 0.0` の block 内でのみ read されます（`2736`）。`--pcie-frac` を与えると block 全体が skip され、この変数は効きません。
- canonical pack であること（`!native_pack`）。native pack は常に probe されます（`2752` の `native_pack ||`）。
- probe が成功すること。`pf_old_canon` が false のとき `probe_pcie_h2d_gbps` を呼ぶ（`2752`）。返りが 0 以下なら `o.pcie_frac = base`（0.2）で auto は設定されません（`2753-2754`）。
- PcieAuto が実際に走る条件: `o.pcie_frac_auto && !all_experts_resident && o.batch == 0 && o.peer_device < 0 && (n_stages == 1 || pcie_auto_split_ok())`（`src/program/generate.cpp:8242`）。`pcie_frac_auto` は probe 成功時に `(layer_split empty || pcie_auto_split_ok()) && decode_defaults_arch_ok() && !pf_old` で設定されます（`2767`）。`decode_defaults_arch_ok()` は CUDA で常に true、HIP で gfx1200/gfx1201 のときだけ true（`1571-1580`）。`pcie_auto_split_ok()` は `STRATA_PCIE_AUTO_SPLIT` の `atoi != 0`（`1564-1567`）。

つまり Windows で `=1` を設定すると、`STRATA_PCIE_FRAC_DEFAULT=old` で上書きされない限り、canonical pack の share が probe され、PcieAuto の refine が有効になります。設定しない（既定）と probe せず share は 0.2 のまま、`pcie_frac_auto` は false です。

## 実行時の詳細

`base = native_pack ? 0.55 : 0.2`（`2737`）。`pf_old_canon` が true（Windows 既定）なら `bw = -1.0`、`o.pcie_frac = base`（0.2）になり、`pcie_frac_auto` は設定されません。`pf_old_canon` が false で probe 成功なら `o.pcie_frac = pcie_frac_for_gbps(bw, base)`（`base * min(1, gbps/20)`、`1656-1658`）で、`pcie_frac_auto` が true になります。PcieAuto は最初の decode window 群で CPU pool の speed から share を refine します（`1660-1668`、最大 3 回の update、0.05 step 丸め）。

ログ（canonical pack が probe されたとき）: `strata generate: PCIe probe: %.1f GB/s host->device (best of %s); the canonical pack starts at pcie_frac 0.20 and refines it from the CPU pool's speed`（`2757-2758`）。probe 失敗時: `strata generate: PCIe probe failed -> pcie_frac default 0.20`（`2771`）。native pack 経由の refine: `-> pcie_frac %.2f (default %.2f)`（`2765-2766`）。この変数自身の専用ログはありません。

## 測定値

`docs/DETAILS.md:1653` の記載: canonical Q2_0 pack は 0.1.43 から CUDA で PcieAuto を使う。Linux では既定、Windows では `STRATA_PCIE_AUTO_CANON=1`（opt-in）。RTX 5070（Windows）で code +2.5%、short answer -3.3%。constant 1.85 は 3 machine への fit で、各 machine の best に step 内で収まる（best 上ではない）。これは記載された測定環境での値であり、他の機種の性能を保証しません。

## 根拠

- read と分岐: `src/program/generate.cpp:2741-2744`（Windows CUDA 限定）、`pf_old` `2739-2740`、`base` `2737`、probe 条件 `2752`、`pcie_frac_auto` 設定 `2767`。
- `--pcie-frac` 既定と skip: `src/program/generate.cpp:575`、`2736`、`1996`。
- PcieAuto の実行条件: `src/program/generate.cpp:8242`、`1656-1668`、`1564-1567`、`1571-1580`。
- ログ文言: `src/program/generate.cpp:2757-2758,2765-2766,2771`。
- docs 照合: `docs/DETAILS.md:1653`。
