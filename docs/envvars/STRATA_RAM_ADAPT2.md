# `STRATA_RAM_ADAPT2`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`strata serve` の resident RAM mode で、RAM に置く expert の選択を会話中のルーティングに合わせて更新します。GPU cache にない expert のうち、直近の decode window で使われた候補を RAM に読み込み、同じ layer の RAM 内で使われていない expert と入れ替えます。RAM 使用量は増やさず、読み込みは専用 I/O thread に先行させます。

`STRATA_RAM_ADAPT` が実装する同期読み込み経路を置き換える変数ではありません。新経路では両方の変数を有効にする必要があります。`STRATA_RAM_ADAPT2` だけでは promotions の選定・stage は行われません。

## 値と判定

| `STRATA_RAM_ADAPT2` | 結果 |
|---|---|
| unset | 無効 |
| `atoi` の結果が `0` | 無効。空文字、数字で始まらない文字列、`0` で始まる整数など |
| `atoi` の結果が 0 以外 | 有効。負数も有効 |

文字列全体を検証せず、C/C++ の `std::atoi` で変換します。したがって、先頭の空白や符号の後の整数部分が変換され、後続文字は判定に使われません（例: `1xyz` は有効、`0xyz` は無効）。変換エラーを別扱いする処理はありません。

有効化後に同じブロックで読み込む関連設定の既定値と変換は次のとおりです。

| 変数 | 既定値 | 設定時の処理 |
|---|---:|---|
| `STRATA_RAM_ADAPT_PROMPT_W` | `0.25` | `atof` 後、下限 0 に clamp。プロンプト routing の seed の重み |
| `STRATA_RAM_ADAPT_CACHED_W` | `0.15` | `atof` 後、0〜1 に clamp。page cache にある候補の miss cost の重み |
| `STRATA_RAM_ADAPT_PER_LAYER` | `2` | `atoi` 後、下限 1。各 layer の候補上限 |
| `STRATA_RAM_ADAPT_SKIP_TOP` | `2` | `atoi` 後、下限 0。GPU tier が取り込みそうな上位候補を選定から除く数 |

これらの関連設定は `STRATA_RAM_ADAPT2` が無効でも初期値を更新しますが、主変数が無効なら機能には使われません。

## 有効になる条件

値が有効でも、実際の入れ替えにはすべて次の条件が必要です。

- `strata serve` の window 処理である。
- `STRATA_RAM_ADAPT` が正数（unset は 0）。この値は最大で何件の promotion を一度に stage するかにも使われる。
- 最初の window の後で、decode usage が存在し、adaptive swap が pending でない。
- 非同期 adaptive round が実行中でない。
- resident RAM copy が利用可能（`src.complement_ready()`）。
- single GPU で、peer device / remote expert optimization がなく、`--batch` が 0。

layer split、peer/helper GPU、batch serve ではこの選定・stage 経路に入りません。`STRATA_EXCHANGE_ROTATE` などにより RAM copy の place を入れ替えられない場合、個別の install は失敗して skip されます。

## 実行時の詳細

主変数と4つの関連重みは serve の初期化中に `getenv` で読み、serve 内の `RamAdapt2` 状態に保存します。serve 起動後の環境変更は再評価されません。`STRATA_RAM_ADAPT` は最初の対象 window 境界で `static` 初期化され、プロセス内で一度だけ読みます。

有効な経路では各 decode window の境界で、まず完了済みの staged reads を RAM copy に install します。続いて、layer ごとに GPU cache 外の候補と RAM に resident な候補を usage から評価します。候補 expert の基礎値は decode usage と prompt routing の seed の和で、値が 2 未満の非 resident 候補は除外されます。page cache にある候補には `STRATA_RAM_ADAPT_CACHED_W` を掛け、RAM 内候補のうち低いものと比べます。`STRATA_RAM_ADAPT_SKIP_TOP` は GPU tier が選びそうな decode usage 上位を先に除外します。最大 `STRATA_RAM_ADAPT_PER_LAYER` ペア/layer を候補にし、利得を blob byte 当たりで比較して全体順位を作り、`STRATA_RAM_ADAPT` の件数まで stage します。prompt の routing は `STRATA_RAM_ADAPT_PROMPT_W` で seed に反映され、seed は各後続 window で 0.95 倍に減衰します。

`ram_stage` は I/O thread を起動し、ファイルから新 expert の blob を読みます。read が完了した job は次の対象 window 境界で install されます。install 時に GPU tier が対象 expert のいずれかを取得済みなら skip し、読み込み失敗や RAM copy への install 不可も skip されます。これにより RAM copy を更新するのは window 間であり、window 実行中の RAM read と place の書き換えを重ねません。後続 prompt にも更新後の resident RAM copy が使われます。

stage queue の上限は関連変数 `STRATA_RAM_ADAPT_QUEUE` で決まり、既定値は 64、設定値は `atoi` 後に最低 1 へ clamp されます。値は最初の `ram_stage` 呼び出しで static cache されます。queue が満杯、同じ layer の重複 job、または RAM copy が無い場合は `ram_stage` が false を返し、その候補はその境界では stage されません。

serve 終了時の累積ログは `strata serve: resident RAM (STRATA_RAM_ADAPT2): %lld promotions read on the I/O thread, %lld installed, %lld skipped at the install (%lld of them: the GPU tier took one of the pair)` です。これは staged read / install / skip の件数で、性能値ではありません。

## 文書との照合

`docs/DETAILS.md:172-181` は `STRATA_RAM_ADAPT` による同期読み込み方式を記載しています。今回確認した `STRATA_RAM_ADAPT2` の先読み、prompt seed、複数候補選定の実装説明はその記述にはありません。同資料の測定値は旧 `STRATA_RAM_ADAPT` の説明箇所にあるため、ここでは `STRATA_RAM_ADAPT2` の性能値として扱いません。

## 根拠

- `src/program/generate.cpp:8266-8283` — 主変数と関連設定の読み取り、既定値、変換・clamp。
- `src/program/generate.cpp:10831-10843` — prompt routing seed の収集。
- `src/program/generate.cpp:14801-14877` — `STRATA_RAM_ADAPT` との併用条件、候補評価、install と次回分の stage。
- `src/program/generate.cpp:15368-15372` — serve 終了時の累積ログ。
- `src/core/expert_source.cpp:4368-4393,4402-4455` — queue への登録、I/O thread の読み込み、window 境界での install と skip。
- `src/core/expert_source.cpp:4370-4389` — `STRATA_RAM_ADAPT_QUEUE` の queue 上限と stage 拒否条件。
- `src/core/expert_source.cpp:4346-4365` — resident copy の範囲検査と実際の place 更新。
- `include/strata/core/expert_source.hpp:823-832` — stage/install の契約とカウンター。
- `docs/DETAILS.md:172-189` — 既存資料にある `STRATA_RAM_ADAPT` の説明と、その測定対象。
