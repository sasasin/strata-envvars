# `STRATA_ADAPT_PICK_INLINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert arena を使う非同期 adaptive tier で、次の swap 候補を選ぶ `a_pick()` を decode loop の thread 上で実行するか、job thread に渡すかを選びます。未設定時は inline が既定です。これは adaptive tier 自体を有効にする設定ではなく、選択処理を行う thread の設定です。

## 値と判定

ローカル helper `a_env(name, def)` は、変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を返します。`STRATA_ADAPT_PICK_INLINE` の既定値は `1` です。変換結果が 0 なら inline を使わず、0 以外なら使います。

| 環境値 | `atoi` の結果 | 選択処理 |
|---|---:|---|
| 未設定 | 既定値 `1` | inline |
| 空文字 | 既定値 `1` | inline |
| `0`、`false`、数値で始まらない文字列 | `0` | job thread |
| `1`、`-1`、`2` | 非ゼロ | inline |
| 数字の後ろに文字が続く値（例: `1abc`） | 数字部分の変換値 | 変換結果が非ゼロなら inline |

文字列全体の妥当性検査はありません。`atoi` が先頭の空白や符号、数字の prefix を処理するため、たとえば ` 1tail` は inline、`0tail` は job thread になります。値を読み取るのは adaptive 非同期処理の設定時で、`static` cache ではありません。実行中に環境値を変えてもこの実行の `a_inline` は再評価されません。

根拠: `src/program/generate.cpp:11689-11697`。

## 有効になる条件

- `srcp == &arena_src`（expert arena）でなければ、`a_inline` は環境値にかかわらず false です。resident RAM mode など arena 以外の source では、この設定で選択 thread は切り替わりません。
- arena モードの非同期 adaptive tier が実際に動き、`ajob` が作られている必要があります。adaptive tier には `--adapt-every` と `--adapt-swaps` が必要です。
- `--adapt-async 1` なら非同期 tier を明示できます。`--adapt-async` を省略した場合は、CUDA build、`--serve`、単一 GPU、arena、batch slot なし、`--pipeline-windows` なし、peer/remote expert なし、overlap tier なし等の条件を満たすとエンジンがセッション中の測定に基づいて非同期 tier を試すことがあります。`--adapt-async 0` または `STRATA_ADAPT_ASYNC=0` ではこの自動選択を止めます。
- `--pipeline-windows 2` と layer split は arena の非同期 tier の対象外です。非同期 tier 自体が条件により無効なら、この変数の値に関係なく効果はありません。

CUDA の自動選択条件は `include/strata/core/adapt_async_default.hpp:19-55`、呼び出し側の条件設定は `src/program/generate.cpp:9026-9045` にあります。明示指定時などの無効化理由は `src/program/generate.cpp:9047-9062` に記録されています。

## 実行時の詳細

非同期 round の開始時、inline が有効ならその tick で `a_pick()` を直接実行してから copy-in の段階へ進みます。無効なら `a_pick()` を job thread に post し、次の状態処理で選択完了を待ちます。arena の round は copy-back や RAM 上の交換を行わず、選ばれた expert の GPU への copy-in を進めます。したがって、この変数が変えるのは選択処理の実行場所であり、候補選定規則や環境値の数値による swap 数ではありません。

設定は arena と async tier の初期化時に一度評価されます。adaptive round ごとに環境を読み直す処理はありません。終了時、async tier が使われた arena 実行では stderr に `pick inline` または `pick on the job` と平均選択時間（`ms/round`）を含む統計行が出ます。変数専用の警告やエラー分岐はありません。copy-in の CUDA エラー等は共通の非同期 tier 経路でログに記録され、tick 側へ失敗を返します。通常の decode loop は `ERR an adaptive refill failed` を出して失敗を返し、pipelined loop は stderr に `strata serve: pipelined decode: an adaptive refill failed` を出し、終了コード 1 の経路に入ります。

根拠: `src/program/generate.cpp:11655-11667,11888-11926,11934-11989,12831-12836,16169-16180,16384-16390,16952-16955,17510-17519`。

## 根拠

- 環境値を読む helper と `a_inline` の定義: `src/program/generate.cpp:11689-11697`。
- async round 開始時の inline / job thread 分岐: `src/program/generate.cpp:11901-11926`。
- arena の copy-in 元と CUDA copy-in の失敗ログ: `src/program/generate.cpp:11788-11820`。
- arena/async tier の前提と CUDA の自動選択条件: `include/strata/core/adapt_async_default.hpp:19-55`, `src/program/generate.cpp:9026-9062`。
- async tier の終了時統計行: `src/program/generate.cpp:17510-17519`。
- refill 失敗の返却・表示経路: `src/program/generate.cpp:11779-11819,12831-12836,16169-16180,16384-16390,16952-16955`。
