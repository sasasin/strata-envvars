# `STRATA_PIPELINE_AUTO_MIN_STAGES`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。Strata 所有ソースを対象とし、外部ライブラリの環境変数の意味は扱わない。

## 役割

`--pipeline-windows` を指定しない場合に、パイプライン windows を自動で有効にするために必要な layer split の最小 stage 数を指定する。既定値は 3 stage。値を下げると、他の有効条件を満たす環境で 2 stage split も自動有効化の候補になる。値を上げると、より多くの stage がある split に限って自動有効化される。

この変数はパイプラインを単独で ON にするスイッチではない。また `--pipeline-windows N` を明示した場合には参照されない。

## 値と判定

環境変数は `std::getenv` で取得し、設定されていれば `std::atoi` で変換した値と 2 の大きい方を stage 下限として使う。文字列全体の数値検証や上限 clamp はない。`atoi` は先頭の空白と符号を許し、数字列の後ろにある文字を無視する。数値変換できない場合は 0 となり、最小値 2 が適用される。

| 環境変数の状態・値 | stage 下限 |
|---|---:|
| 未設定 | 3 |
| 空文字、数値で始まらない文字列 | 2 |
| `0`, `1`, 負数 | 2 |
| `2` 以上の整数 | その整数 |
| 数字の後ろに文字がある値（例: `4abc`） | 数字部分（例では 4） |

したがって `STRATA_PIPELINE_AUTO_MIN_STAGES=0` は自動機能の OFF 指定ではなく、stage 下限を 2 にする。整数として表せない値の変換結果については、ソースに明示的なエラー処理がない。

## 有効になる条件

この値が参照されるのは `o.pipeline_windows < 0` の自動判定時だけである。オプション構造体の初期値は `-1` で、CLI の `--pipeline-windows N` は値を 0..2 に clamp して設定するため、明示指定はこの環境変数の判定を迂回する。

自動で `--pipeline-windows 2` になるには、stage 下限に加えて以下をすべて満たす必要がある。

- `--serve` を使っている。
- 複数 GPU の layer split で、stage が同一 GPU を共有していない。
- stage 数（`split_devs.size() + 1`）がこの変数から得る下限以上。
- `STRATA_PIPELINE_AUTO` が設定されていないか、`atoi` の結果が 0 でない。
- HIP ビルドであり、現在の GPU が `decode_defaults_arch_ok()` の判定を通る（gfx12 WMMA architecture）。CUDA ビルドではこの自動判定を常に OFF にする。
- MTP drafter があり、`--spec` が 2 以上。
- `--batch` slots を使っていない。
- `--peer-device` を使っておらず、remote/helper expert cache もない。
- `--adapt-async` を使っていない。

条件を満たして有効化されたときは stderr に `strata generate: --pipeline-windows 2 is on by default for a layer split of ... stages (--pipeline-windows 0 or STRATA_PIPELINE_AUTO=0 turns it off)` が出る。自動判定で条件不足なら `pipeline_windows` は 0 になり、この段階では理由ログを出さない。

## 実行時の詳細

`generate.cpp` の layer split 準備中、各 stage の expert cache サイズを決める前に自動判定される。`STRATA_PIPELINE_AUTO_MIN_STAGES` の `getenv` 結果ポインタはブロックスコープの `static` に保存され、最初に自動判定ブロックを通った時に取得される。後続の自動判定が同一プロセスで再度あれば同じ環境文字列ポインタを使う。stage 下限への `atoi` 変換自体は判定ブロックを通るたびに行われる。

有効な場合、値は `o.pipeline_windows = 2` に反映されます。これは stage 0 が次の speculative decode window を先行実行し、最後の stage が現在の window を検証する経路です。予測が外れたときに前段の状態を戻します。無効時は値は 0 となり、stage は window ごとに順番に動きます。機能の詳細は `docs/MULTI_GPU.md` に記載されています。

## 根拠

- `src/program/generate.cpp:647-652`: `pipeline_windows` の初期値 `-1` と `--pipeline-windows` の意味。
- `src/program/generate.cpp:2075`: 明示 CLI 値を `atoi` し、0..2 に clamp。
- `src/program/generate.cpp:3391-3413`: 自動判定、環境変数読み取り、`atoi`、stage 下限、backend・機能条件、および有効時のログ。
- `src/program/generate.cpp:1607-1618`: HIP の `decode_defaults_arch_ok()` が gfx12 WMMA architecture を確認し、非 HIP では true を返す定義。自動判定側は非 HIP を別途 OFF にする。
- `docs/MULTI_GPU.md:246-256`: AMD RDNA4 gfx1200/gfx1201 の `--serve` で 3 stage 以上を既定有効とする説明、手動 OFF、他の条件。文書にはこの環境変数による閾値変更の説明はなく、閾値と追加条件の根拠は現行ソースに従った。
