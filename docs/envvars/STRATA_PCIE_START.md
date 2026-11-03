# `STRATA_PCIE_START`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

自動調整される PCIe expert share の起動時初期値を選びます。新方式は CPU pool の worker 数を見込んだ値から始め、旧方式は直前に決まった link 基準の share を保ちます。以降の decode window で `PcieAuto` が share を調整する経路では、この変数は初期値を変えるだけです。

## 値と判定

この変数は `std::getenv` で読み、文字列全体を `std::strcmp` で比較します。空文字、大小文字違い、余分な文字は特別扱いされず、表の「その他」に入ります。

| ビルド | unset | 値が完全一致する場合 | その他の設定値（空文字を含む） |
|---|---|---|---|
| HIP (`STRATA_USE_HIP`) | 旧方式 | `new` で新方式 | 旧方式 |
| HIP 以外（この実装の CUDA 経路） | 新方式 | `old` で旧方式 | 新方式 |

たとえば HIP では `new ` や `NEW` は旧方式、CUDA では `old ` や `OLD` は新方式です。数値変換や無効値エラーはありません。

新方式の初期 share は、`R = min(65, 4 × pool.workers())`、`f0 = link / (link + 1.85 × R)` を 0.05 刻みに丸め、0.10〜0.60 に制限した値です。旧方式では、この環境変数による代入を行わず、先に設定された `o.pcie_frac` が残ります。

## 有効になる条件

値判定に進むには、`o.pcie_frac_auto` が true かつ PCIe probe の `o.pcie_probe_gbps` が正である必要があります。`--pcie-frac` が指定されると `o.pcie_frac` は非負になり、自動 share 初期化ブロックに入らないため、この変数は効果を持ちません。

自動化の設定は backend・モデル・probe によって異なります。native pack では probe 成功後、`STRATA_PCIE_FRAC_DEFAULT=old` でなく、`decode_defaults_arch_ok()` または `pcie_auto_fork_arch_ok()` が成立し、layer split なら `pcie_auto_split_ok()` も成立する場合に `pcie_frac_auto` が有効になります。CUDA の canonical pack は `STRATA_PCIE_FRAC_DEFAULT=old` でなく probe に成功した場合に自動調整対象になります。Windows CUDA ではさらに `STRATA_PCIE_AUTO_CANON=1` が必要です。layer split ではいずれも同じ split 条件を適用します。HIP の canonical pack は自動調整対象外です。probe 失敗時は既定 share を使い、対象変数による初期値変更はありません。

## 実行時の詳細

Strata は server 側で `o.pcie_frac_auto` と正の probe 値を確認した後に環境を読みます。値は static cache されず、この初期化ブロックを通るたびに取得されます。新方式を選ぶと stderr に `strata serve: PCIe share: start ...` の行を出し、算出した `f0` を `o.pcie_frac` に設定します。旧方式または条件不成立ではこの起動ログと代入はありません。

後続の `PcieAuto` が稼働する場合、decode window の測定から share を再計算し、変更時に `strata serve: PCIe share: ... -> pcie_frac ...` を stderr に出します。これは起動初期値とは別の調整です。`--pcie-frac` が明示されている場合はこの自動 share 経路も設定されません。コード上、この変数の値が無効であることを理由とした警告・終了・fallback はありません。

コメントには性能および token 再現性に関する測定メモがありますが、本書ではコードで確認できる分岐と計算のみを記載し、測定結果を一般化しません。

## 根拠

- 候補名の唯一の完全一致参照と値判定、式、起動ログ、share 上書き: `src/program/generate.cpp:12142-12165`。
- `--pcie-frac` の既定値と自動化フラグの意味: `src/program/generate.cpp:869-871`。
- 明示 `--pcie-frac` の判定: `src/program/generate.cpp:3502,3901-3903`。
- probe・モデル・backend・既定環境変数に応じた `pcie_frac_auto` 設定: `src/program/generate.cpp:4567-4610`。
- `PcieAuto` の係数、計算、および後続 window 更新ログ: `src/program/generate.cpp:2638-2670,12227-12255`。
