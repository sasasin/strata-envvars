# `STRATA_PIPELINE_AUTO`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数の意味は含めない。

## 役割

`--pipeline-windows` を省略した場合に行う自動選択を抑止します。値が非ゼロでも pipeline を強制的に有効にはしません。サーバーモード、対応する HIP GPU、十分な段数などの条件を満たしたときだけ自動で `--pipeline-windows 2` になり、この変数はその選択を止める用途です。

`--pipeline-windows` を明示した場合、この環境変数は自動選択の判定に使われません。たとえば `--pipeline-windows 2` は環境変数が `0` でも要求値として検査され、`--pipeline-windows 0` は環境変数の値に関係なく無効です。

## 値と判定

自動選択ブロックで `std::getenv("STRATA_PIPELINE_AUTO")` の結果を `std::atoi` に渡し、結果が `0` かどうかを判定します。文字列全体の妥当性検査はありません。

| 環境変数の状態・値 | `atoi` 結果の扱い | 自動選択への影響 |
|---|---:|---|
| 未設定 | 判定上の veto なし | 他の条件を満たせば自動 ON になり得る |
| 空文字 | `0` | 自動選択を止める |
| `0`、`00`、`0abc` | `0` | 自動選択を止める |
| `1`、`-1`、`2` | 非ゼロ | veto しない。自動 ON を保証しない |
| `abc`、空白だけなど、数値変換が 0 になる文字列 | `0` | 自動選択を止める |
| 数字で始まり、その後に文字が続く値（例: `1abc`） | 数字部分の値 | その値が非ゼロなら veto しない |

先頭の空白や符号を含む文字列も `atoi` の変換規則に従います。大文字小文字の比較はありません。変換可能な数値の範囲外の文字列に対する `atoi` の結果は、この実装で定義していません。

## 有効になる条件

この変数が未設定、または `atoi` の結果が非ゼロであっても、自動で値が `2` になるにはすべて次を満たす必要があります。

- `--pipeline-windows` が省略されている（内部値 `-1`）。明示指定時はこの環境変数を読んで自動選択しません。
- `--serve` と複数 GPU の layer split を使い、同じ GPU に複数 stage を置く split ではない。
- stage 数が `STRATA_PIPELINE_AUTO_MIN_STAGES` 以上。後者が未設定なら 3。設定時は `atoi` し、最小値を 2 に clamp します。
- HIP build で、現在の GPU の arch 名が gfx12 WMMA 対応として認識される。CUDA build では自動選択を常に OFF にします。
- MTP drafter があり、`--spec` が 2 以上である。
- `--batch` が 0、`--peer-device` が未指定、helper expert cache がなく、`--adapt-async` が無効。

いずれかの条件を満たさなければ、自動値は `0` です。自動選択が成立したとき stderr に `strata generate: --pipeline-windows 2 is on by default for a layer split of N stages (--pipeline-windows 0 or STRATA_PIPELINE_AUTO=0 turns it off)` が出ます。自動選択が成立しない場合、この経路から無効理由のログは出ません。

自動選択ではない経路で `--pipeline-windows` が正値の場合は別途適用条件を検査し、条件外なら `strata generate: --pipeline-windows N is off: ...` を stderr に出して 0 に戻します。

## 実行時の詳細

環境変数は layer split の設定後、stage の重い cache や pipeline 用資源を確保する前に、生成プロセスの起動設定として判定されます。`std::getenv` のポインタを関数内 static 変数に初回評価時保存します。したがって、初回の自動選択評価後にプロセス環境を変更しても再読込されません。`STRATA_PIPELINE_AUTO_MIN_STAGES` も同じ位置で static に保存されます。

値が自動で `2` になった場合、pipeline は stage 間で verify window を重ね、stage 0 が次の window を先行実行しながら最終 stage が現在の window を検証する decode 経路を選びます。推測が外れた場合の state restore を含む詳しい処理は `src/program/generate.cpp` の pipeline decode loop と `include/strata/core/verify.hpp` の pipelined verifier にあります。この文書は環境変数がその経路を選ぶ条件を記述し、性能向上を一般化しません。

## 資料との照合

`docs/MULTI_GPU.md` は 0.1.43 以降、AMD RDNA4（gfx1200 / gfx1201）、`--serve`、draft layer、3 stages 以上で既定有効とし、`STRATA_PIPELINE_AUTO=0` を opt-out と説明しています。現行ソースも既定の最小 stage 数を 3 とし、HIP で gfx12 arch を確認します。資料にある2 stage の損失や4x R9700 での測定はその記載条件での測定結果であり、この環境変数単体が速度を保証するものではありません。

## 根拠

- `src/program/generate.cpp:647-652` — `pipeline_windows` の内部既定値 `-1` とオプションの意味。
- `src/program/generate.cpp:2075` — `--pipeline-windows` 明示時の parse と 0..2 への clamp。
- `src/program/generate.cpp:3390-3431` — 自動判定、環境変数の読み取り、既定 stage 数、HIP/CUDA 分岐、条件、ログと明示値の検査。
- `src/program/generate.cpp:1607-1617` — HIP の gfx12 arch 判定。CUDA build では `true` を返す helper だが、自動選択部の CUDA 分岐が `on = false` にする。
- `src/program/generate.cpp:7471-7491, 7695-7728, 11305-11321` — pipeline verifier と decode loop の初期化・実行箇所。
- `docs/MULTI_GPU.md:246-267, 302-306` — 既定条件、動作説明、測定条件。
