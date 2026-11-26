# `STRATA_SPLIT_EARLY_OFF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve --layer-split auto` の初期化中、GPU の空き VRAM に基づいて重みをロードする前に split を決める early spill walk を抑止する。対象変数は値を parse せず、`std::getenv(...) == nullptr` かどうかだけを判定するため、環境に存在すると値が空でも early walk に入らない。対象変数が設定されていても、重みロード後に後段 GPU の空き容量を調べる spill walk は別の条件で実行されうる。このため、全ての stage trim や layer split を無効にするスイッチではない（`engine/src/program/generate.cpp:5843-5856, 6069-6102`）。

early walk は split-auto 時に全 GPU の空き容量などを重みロード前に見て、容量が足りない場合は split を具体化する処理である。実際の layer split は server mode でのみ受け付けられる（`engine/src/program/generate.cpp:4774-4807, 4848-4856`）。

## 値と判定

対象箇所は `std::getenv("STRATA_SPLIT_EARLY_OFF") == nullptr` の有無判定だけで、文字列変換・比較はない（`engine/src/program/generate.cpp:5854-5856`）。

| 条件 | unset | 設定時に early walk を許す値 | early walk を抑止する値 |
| --- | --- | --- | --- |
| 共通 | 条件式を通過しうる | なし | 空文字、`0`、`1`、`false`、その他全ての値（設定されているだけで抑止） |

unset でも他の条件を満たさなければ walk は実行されない。別の設定である `STRATA_STAGE_TRIM` は同じ関数内で独立に評価され、空文字は trim 要求にならない一方、文字列 `"0"` は early walk を止める。CLI の `--trim-stage-weights` は `trim_user_asked` を真にし early walk の条件から外す。`--no-trim-stage-weights` はそのフラグ値を 0 にするが、early walk の条件式にはフラグ値そのものの検査がない（`engine/src/program/generate.cpp:4039-4044, 4118-4121, 5836-5841, 5854-5856`）。

## 有効になる条件

変数が unset の場合に early walk が実行されるには、次を全て満たす必要がある（`engine/src/program/generate.cpp:5854-5856`）。

- `--serve` と `--layer-split auto` によって複数 GPU の split が有効で、後段 GPU が少なくとも 1 台あること（`engine/src/program/generate.cpp:4803-4807, 4856`）。
- `--trim-stage-weights` や `STRATA_STAGE_TRIM` による trim の明示要求がないこと（`trim_user_asked == false`）。
- `STRATA_SPILL_OFF` が unset であること。設定値の内容ではなく設定有無で判定する。
- `STRATA_STAGE_TRIM` が文字列 `"0"` ではないこと。
- `spill_discrete_gpu()` が true であること。Metal build では `strata::spill_allowed(true, false)`、それ以外では CUDA device/property を取得して discrete GPU について `strata::spill_allowed(false, integrated)` を呼ぶ。device 情報を取得できない場合は false になる（`engine/src/program/generate.cpp:326-339`）。

early walk ではモデルの dense weight pool サイズを得られた場合に、GPU ごとの free VRAM を見て trim の要否を判定する。プールサイズ取得に失敗した場合はこの事前 walk の容量判定に進まない（`engine/src/program/generate.cpp:5858-5885`）。

## 実行時の詳細

対象変数は `generate.cpp` の layer split 初期化中に通常の `getenv` で一度検査され、static cache には保存されない。後からプロセス環境を変えても、この判定を通過した後の処理へ遡って反映されない（`engine/src/program/generate.cpp:5843-5856`）。

early walk が有効で、空き容量から trim が必要と判定されると、split を空き容量から選び直す。GPU を減らす必要があれば対象カードを外し、他カードに割り当てられない場合は単一 GPU 実行へ切り替える場合もある（`engine/src/program/generate.cpp:5886-5914`）。対象変数を設定して early walk を抑止した場合、`--layer-split auto` は既存の順序で進み、CUDA0 の重みをロードした後に別の容量判定が行われる。後段 GPU に十分な空きがない場合は、そこでは後段の重みを stage の担当 layer 分だけに trim できる。後段 walk に `STRATA_SPLIT_EARLY_OFF` の再検査はない（`engine/src/program/generate.cpp:5945-5960, 6069-6102`）。

この後段判定は `multi_gpu` で後段 GPU があり、`STRATA_SPILL_OFF` が unset、`STRATA_STAGE_TRIM` が `"0"` でなく、`spill_discrete_gpu()` が true の場合に行われる。early walk を止める変数の設定だけでは、この後段判定を止めない（`engine/src/program/generate.cpp:6074-6102`）。

## ログと測定値

この変数の設定・未設定だけを知らせるログはない。early walk が容量不足を検出した場合は `short of GPU memory` を含む行が出力され、カード除外や split 選択を報告する（`engine/src/program/generate.cpp:5900-5908, 5932-5936`）。early walk を抑止した場合でも、後段 walk が容量不足を検出すれば `short of GPU memory: CUDA%d has ...` の行が出る（`engine/src/program/generate.cpp:6090-6095`）。この変数による終了・エラー経路は確認できない。

## 根拠

- `engine/src/program/generate.cpp:326-339` — spill 対象となる GPU の判定。
- `engine/src/program/generate.cpp:4774-4807, 4848-4856` — server mode、`--layer-split auto`、複数 GPU の条件。
- `engine/src/program/generate.cpp:5836-5856` — stage trim の値と優先、対象変数の唯一の実読み取り箇所。
- `engine/src/program/generate.cpp:5858-5943` — early walk の容量判定と split 変更。
- `engine/src/program/generate.cpp:6069-6102` — 後段 walk と対象変数による抑止の対象外であること。

`docs/MULTI_GPU.md:215-230` は小容量 GPU の trim / split walk の概要を説明しており、ソースの処理順と一致する。候補一覧 `terminal/data/settings-register.json:45947-45957` も backend を `cuda-hip`、読み取り位置を `generate.cpp:5856` として登録している。設定 registry の記載は実装根拠ではなく、実読み取りは上記のソース分岐で確認した。
