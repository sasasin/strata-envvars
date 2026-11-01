# `DS4_ASYNC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek 4.1 (`src/dsv41/ds4_model.cu`) の `STRATA_METAL` ビルドで、モデルの window 処理を mailbox を使う async 経路にするかどうかを切り替えます。`DS4_ASYNC` が未設定なら同期経路、設定されていれば（値の内容に関係なく）async 経路を選べる状態になります。ただし window の行数上限 `DS4_ASYNC_T` と、処理経路ごとの上書き条件も適用されます。

## 値と判定

| ビルド・条件 | `DS4_ASYNC` 未設定 | `DS4_ASYNC` 設定あり |
|---|---|---|
| `STRATA_METAL` 定義あり | `sync_decode = true`。通常の window は同期経路 | `sync_decode = false`。`DS4_ASYNC_T` 以下の通常 window は async 経路を選べる |
| `STRATA_METAL` 定義なし | この変数は読まれず、挙動に影響しない | 同左 |

Metal 側は `getenv(...) == nullptr` だけで判定し、文字列を parse しません。従って `DS4_ASYNC=0`、空文字、`false` も「設定あり」となり、async を許可します。値の大小、空白、大文字小文字による違いはありません。

上限は別変数 `DS4_ASYNC_T` で、未設定時は 8、設定時は `atoi` の結果です。`T <= async_max_t` のときだけ通常経路の async 条件を満たすため、0・負値・数値に変換できない文字列は正の `T` に対して上限条件を満たしません。数値の後ろに続く文字列は `atoi` が解釈できる先頭部分だけが使われます。CLI オプションによる `DS4_ASYNC` の上書きは見つかりません。

## 有効になる条件

- `DS4_ASYNC` の読み取り自体は `#if defined(STRATA_METAL)` の枝にだけあります。CUDA/HIP などこの macro がないビルドでは `DS4_ASYNC` は無効な設定名です。その枝では代わりに `DS4_SYNC` の設定有無で `sync_decode` を決めます。`DS4_SYNC` は値を見ず、空文字を含め設定されていれば同期指定になります。
- 通常の `plan_window()` では `wp.async = par || (!sync_decode && T <= async_max_t)` です。`par` が真なら `DS4_ASYNC` / `DS4_ASYNC_T` の同期条件を通らず async を選びます。
- `draft_()` の drafter window は `dp.async = !sync_decode && T <= async_max_t` で、`par` による上書きはありません。
- 2 つの chunk pipeline 経路は `WinPlan` に `wp.async = true` を直接設定します。この経路では `DS4_ASYNC` / `DS4_ASYNC_T` の値で async を止めません。
- 通常 window の `T` が `DS4_ASYNC_T` を超えれば、`DS4_ASYNC` が設定済みでも `par` が偽の経路では同期側になります。

## 実行時の詳細

`sync_decode` は `Model::Impl` のメンバー初期化で評価されます。`Model` の構築時に環境を読み、そのインスタンスの処理で保持します。`static` 変数による cache ではありません。モデル構築後にプロセス環境を書き換えても、その `Impl` の `sync_decode` には反映されません。別の `Model` インスタンスを構築すれば、その時点の環境で初期化されます。`async_max_t` も同じく `Impl` のメンバー初期化時に読み取ります。

async 経路では GPU が routing を mailbox 経由で service thread に公開し、shared expert と VRAM expert の処理を進め、CPU lane の応答は expert の合算前に待ちます。同期側は GPU の routing 結果を host にコピーし、host が選択を処理する経路です。したがってこの変数が変えるのは Strata 内の routing / CPU lane と GPU のスケジューリング経路です。

Strata の `setup.py` は Strix Halo 等の UMA 構成で `DS4_ASYNC` ではなく `DS4_ASYNC_T` を設定ファイルの `env` に書く仕組みを持ちます。既定では 4 を指定し、`STRATA_DSV41_ASYNC_T=8` なら設定を省略して engine の既定 8 に戻します。これは候補変数 `DS4_ASYNC` の値を変更・設定する処理ではありません。

この変数専用のログ、警告、終了・失敗分岐は見つかりません。通常の host-routed 経路には tensor-parallel layer を処理できないエラー (`a tensor-parallel layer on the host-routed path`) がありますが、これは `DS4_ASYNC` の検査や専用エラーではありません。

## 根拠

- `src/dsv41/ds4_model.cu:1126-1136` — `STRATA_METAL` による `DS4_ASYNC` / `DS4_SYNC` の切り替え、`DS4_ASYNC_T` の既定値。
- `src/dsv41/ds4_model.cu:907-915, 920-922, 10698-10701` — `WinPlan`、`Impl`、`Model` の構築と保持期間。
- `src/dsv41/ds4_model.cu:7785-7789` — drafter window の async 判定。
- `src/dsv41/ds4_model.cu:9565-9593` — 通常 window の判定と `par` による上書き。
- `src/dsv41/ds4_model.cu:8610, 8777-8780` — chunk pipeline 経路での async 固定。
- `src/dsv41/ds4_model.cu:10301-10325, 10413-10431` — mailbox 経路と host-routed 経路。
- `setup.py:8376-8388, 8743-8750` — UMA 構成向け `DS4_ASYNC_T` の設定ファイルへの書き込み。
- `docs/DEEPSEEK41.md:51-59` — Strix Halo の記述も `DS4_ASYNC_T=4` と `STRATA_DSV41_ASYNC_T=8` を説明しており、`DS4_ASYNC` 自体の値や意味は文書化していません。
