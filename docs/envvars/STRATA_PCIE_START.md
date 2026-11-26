# `STRATA_PCIE_START`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

PCIe の CPU/GPU expert miss share を自動調整する経路で、最初に使う share を選ぶ。`generate.cpp` は `o.pcie_frac_auto` が真かつリンク帯域の probe 値が正の場合だけこの変数を読み、新しい初期値を選んだ場合は stderr に開始 share を出して `o.pcie_frac` を更新する。`old` を選ぶ場合は、直前に決めた link ベースの初期 share を維持する。これは後続の自動調整を有効化するスイッチではなく、後続の自動調整が使う開始値の選択である（`engine/src/program/generate.cpp:14908-14931`）。

新しい初期値は pool worker 数から仮定する expert-byte rate と probe したリンク帯域で計算される。`r = min(65, 4 * workers)`、`link / (link + pcie_pool_k(r) * r)` を 0.05 刻みに丸め、下限 0.10 と `pcie_share_max()` の上限を適用する。上限および係数は `STRATA_PCIE_SHARE_MAX`、`STRATA_PCIE_K_RULE` と GPU/defaults 条件の影響を受ける（`engine/src/program/generate.cpp:3101-3107,14923-14928`）。

## 値と判定

`std::getenv` の結果を `std::strcmp` で文字列全体と比較する。数値変換、空白除去、部分一致、大文字小文字の変換はしない。未知の文字列を警告する処理もない（`engine/src/program/generate.cpp:14913-14922`）。

| build 条件 | 未設定 | 新しい初期値になる値 | link ベースの初期値を維持する値 |
|---|---|---|---|
| `STRATA_USE_HIP` 定義あり（HIP） | 維持 | 完全一致の `new` | `old`、空文字、`0`、`true`、`NEW` など、それ以外すべて |
| `STRATA_USE_HIP` 定義なし（非 HIP 分岐。通常の CUDA build） | 新しい初期値 | `old` 以外すべて（`new`、空文字、`0`、`true`、`OLD` など） | 完全一致の `old` |

値の有効・無効にかかわらず、この判定自体に fallback エラーや警告はない。`STRATA_PCIE_START` の取得はこの初期化経路で一度行われ、値を static cache するコードはない。後からプロセス環境を書き換えても、すでに計算した `o.pcie_frac` には反映されない（`engine/src/program/generate.cpp:14913-14928`）。

## 有効になる条件

- `--pcie-frac` を指定せず、既定 share の決定処理に入る必要がある。`--pcie-frac` の値が `o.pcie_frac >= 0` なら既定値決定ブロック全体を飛ばすため、この環境変数も読まれない。CLI 引数が優先する（`engine/src/program/generate.cpp:1041-1043,4057,4780-4782,5535`）。
- 既定値決定で自動 share が選ばれ、PCIe probe が成功して `o.pcie_frac_auto == true`、`o.pcie_probe_gbps > 0` となる必要がある。probe 不成立時は既定 share に戻り、`pcie_frac_auto` がセットされないため、この変数の読み取り箇所には到達しない（`engine/src/program/generate.cpp:5535-5580,14913-14914`）。
- 自動 share の適用可否は pack、build、GPU 世代、layer split に依存する。canonical pack は HIP では自動 refinement を設定せず、CUDA では probe 成功かつ layer split なしのときに設定する。Windows CUDA の canonical pack は `STRATA_PCIE_AUTO_CANON=1` が probe 条件に関わる。native pack は CUDA で自動 refinement が設定され、HIP では gfx12 世代や `pcie_auto_fork_arch_ok()` の判定に加えて `STRATA_PCIE_FRAC_DEFAULT` 等の条件が関わる。layer split では `STRATA_PCIE_AUTO_SPLIT` の判定も関わる（`engine/src/program/generate.cpp:2833-2844,2849-2912,5535-5579`）。
- native pack で `STRATA_VERIFY_DEVICE_HITS` が非ゼロ、`STRATA_PCIE_FRAC_DEFAULT=old` ではなく、layer split なし・batch 無効・peer device なしの場合、後続処理が share を `0.00` にし、自動 refinement を無効化する。この条件では起動時の `pcie_frac_auto` が false になり、この変数は読まれない（`engine/src/program/generate.cpp:5581-5588`）。
- 初期 share の更新後に実際の `PcieAuto` refinement が開始する条件はさらに狭い。全 experts が GPU resident でないこと、`batch == 0`、peer device なし、かつ単一 stage または layer split の自動 refinement 許可が必要。これらの条件を満たさなくても、直前の初期値ブロックに到達していれば `STRATA_PCIE_START` による開始 share の変更自体は行われる（`engine/src/program/generate.cpp:14931-14933,15003-15010`）。

## 実行時の詳細

まず probe と既定 share の処理が `o.pcie_frac_auto` と `o.pcie_probe_gbps` を設定する。その後、decode/serve 用 drive の初期化中にこの変数を読み、新しい初期値を選ぶ場合は `o.pcie_frac` と `drive.d.pcie_num` に反映する。`pcie_num` は share を 256 分割に丸めた値で、後続の verifier/drive の PCIe share 設定に使われる（`engine/src/program/generate.cpp:5535-5579,14913-14931`）。

`PcieAuto` が有効なら後続の decode window で CPU pool の miss 処理時間を計測し、条件がそろうと share を再計算する。最初の判定は 12 window 後、それ以降は 48 window ごとで、miss が 300 件未満なら計測を続け、2000 window に達すると停止する。更新は最大 3 回で、変更値は stderr に記録される。これは別の実行時処理であり、`STRATA_PCIE_START` の値を各 request/window で読み直すものではない（`engine/src/program/generate.cpp:3110-3150,15003-15041`）。

明示的な serve request の `pcie_frac=` 指定は request 内の share として別途反映される。`STRATA_PCIE_START` はプロセス起動時の初期 share の選択であり、その request 値を上書きする処理ではない（`engine/src/program/generate.cpp:18859-18870,18922,21441-21446`）。

## ログと測定値

新しい初期値が選ばれたとき、stderr に次の形式で出る。旧初期値を維持した場合、この分岐からのログは出ない（`engine/src/program/generate.cpp:14923-14928`）。

```text
strata serve: PCIe share: start %.2f from %d pool workers (assumed %.0f GB/s of expert bytes) and the %.1f GB/s link (was %.2f)
```

同じソースのコメントには、RTX PRO 5000 mimic・32 workers で初回回答が `+4..+12%`、8 workers と R9700 では `+-1%` と記録されている。また HIP の R9700 について、初期約 50 windows の near-tie token が変わることがあり、旧開始値での比較は `21/45` 対 `45/45` identical answers と記されている。これらは実装コメントの記録であり、測定条件の全容は当該箇所にないため、一般的な性能・出力保証とは扱えない（`engine/src/program/generate.cpp:14908-14918`）。`docs/DETAILS.md` に本変数の追加の測定記述は見つからなかった。

## 根拠

- 読み取り、backend 別の完全一致判定、開始 share の計算・反映: `engine/src/program/generate.cpp:14908-14931`
- CLI の `--pcie-frac` と既定 share / probe / auto 判定: `engine/src/program/generate.cpp:4057,4780-4782,5535-5588`
- auto share の platform/backend 条件と補助環境変数: `engine/src/program/generate.cpp:2833-2912,3101-3107`
- 後続の refinement と条件: `engine/src/program/generate.cpp:3110-3150,15003-15041`
- request ごとの share の適用: `engine/src/program/generate.cpp:18859-18870,18922,21441-21446`
