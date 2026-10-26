# `STRATA_ADAPT_ASYNC`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--adapt-async` をコマンドラインで指定しなかった場合に、適応層（adaptive tier）の非同期方式をセッション中に測定して選ぶ自動判定を止めるための変数です。非ゼロ値は非同期方式を常時有効にする指示ではありません。適用条件を満たす CUDA の実行で、ブロッキング方式を測り、swap 待ちが十分大きい場合だけ非同期方式を試します。

## 値と判定

`adapt_async_env()` は `getenv()` が未設定または空文字なら `-1`（未指定）を返し、それ以外は `std::atoi()` の結果を返します。整数全体の妥当性検査はありません。`atoi` が 0 を返す文字列は、自動選択を止める値として扱われます。

| 環境変数の状態 | 自動選択への影響（CLI 未指定時） |
|---|---|
| 未設定、または空文字 | 미지정相当。以下の適用条件を満たせば自動選択の対象 |
| `0`、`00`、`false`、数値変換できない文字列など、`atoi` が 0 を返す値 | 自動選択を無効化し、通常のブロッキング方式 |
| `1`、`2`、`-1` など、`atoi` が非ゼロを返す値 | 自動選択を許可。適用条件と測定結果に従う |

この変数が `0` でも、CLI の `--adapt-async 1` が指定されていれば CLI 側の明示指定が優先され、環境変数による自動判定の停止は適用されません。`--adapt-async 0` は明示的にブロッキング方式を選びます。

## 有効になる条件

自動選択の対象になるには、CLI オプション未指定かつ `STRATA_ADAPT_ASYNC` の parse 結果が 0 以外であり、さらに次をすべて満たす必要があります。

- CUDA ビルドであること。HIP ビルドは自動選択の対象外です。
- `--serve` で起動していること。
- 適応層が有効であること（`--adapt-every` と `--adapt-swaps` がともに 0 より大きい）。
- 全 expert が RAM arena にあること。
- layer split、`--pipeline-windows`、`--batch` slots、`--peer-device`、`--remote-expert-opt` を使っていないこと。
- `STRATA_ADAPT_OVERLAP` の overlap 方式が有効でないこと。

この判定に通っても、適応層の usage 情報が空ならセッション測定は開始されません。明示的な `--adapt-async 1` は自動選択とは別経路です。実行時に `--serve`、適応層、resident RAM mode または arena などの条件を満たさなければ非同期方式は停止され、stderr に `strata generate: --adapt-async 1 is off (...)` が出ます。pipeline windows と併用する明示指定では、別変数 `STRATA_PIPELINE_ADAPT_ASYNC=0` も非同期方式を停止させます。

## 実行時の詳細

環境変数は engine の初期化時に `adapt_async_env()` で読み、自動選択の可否を決めます。実行中に環境変数を変更しても、この判定は再実行されません。CLI が未指定で自動選択の条件を満たす場合、arena の適応 swap をまずブロッキング方式で実行します。`AdaptAsyncSelf` は最初の64 decode windowをwarm-upとして数え、その後64 window分の時間・token数・適応 swap 待ち時間を集計します。集計した待ち時間が window 時間の5%以上なら、非同期方式を試します。待ちが5%未満ならブロッキング方式のままです。

非同期方式を試す際は4 windowをwarm-upとして除外し、その後64 window分の ms/token を比較します。試行値に `0.98` を掛けた値がブロッキング方式の測定値以下なら、そのセッションでは非同期方式を維持します。条件を満たさなければ helper thread を停止し、ブロッキング方式に戻します。測定対象外のwindowは token 数が0以下、または経過時間が正でない場合です。

自動選択の切り替え時は stderr に次の状態が出ます（数値部分は実行時の測定値です）。

- 非同期方式を試行: `strata serve: adaptive tier: the swaps held the windows up by ...: trying the asynchronous tier for a while`
- 非同期方式を維持: `strata serve: adaptive tier: the asynchronous tier stays on (... ms per token)`
- ブロッキング方式へ復帰: `strata serve: adaptive tier: the asynchronous tier was slower (...): back to the blocking tier for this session`

### 資料との照合

`docs/DETAILS.md:238-240` は `--adapt-async 1` を opt-in と説明しています。一方、調査対象 HEAD の `src/program/generate.cpp` と `include/strata/core/adapt_async_default.hpp` では、CLI 未指定時に条件を満たす CUDA の arena 実行が自動測定の対象です。このため同資料の記述は現行コードの自動選択経路を反映していません。ヘッダーコメントには RTX PRO 5000 と RTX A4000 の測定値が記載されていますが、この調査では測定を再実行しておらず、その数値を独立に検証したものではありません。

## 根拠

- `include/strata/core/adapt_async_default.hpp:19-38`: 判定入力と未設定・空文字・数値変換の処理。
- `include/strata/core/adapt_async_default.hpp:40-55`: CLI 指定、値0、CUDA、serve、適応層、arena、GPU構成などの自動選択条件。
- `include/strata/core/adapt_async_default.hpp:60-101`: warm-up、測定数、待ち比率の閾値、試行値の採否。
- `src/program/generate.cpp:1077-1082,2634`: CLI ヘルプと `--adapt-async` の parse。
- `src/program/generate.cpp:8071-8118`: 環境値の読取、自動判定、明示指定時の実行条件と停止ログ。
- `src/program/generate.cpp:10570-10588`: arena の自動選択時に測定器を起動する条件とブロッキング方式のログ。
- `src/program/generate.cpp:15227-15247`: window ごとの測定更新、非同期試行・維持・復帰ログ。
- `docs/DETAILS.md:238-240`: 既存資料の説明。現行コードとの差は上記「資料との照合」を参照。
