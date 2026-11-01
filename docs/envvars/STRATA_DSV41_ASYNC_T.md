# `STRATA_DSV41_ASYNC_T`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 の setup が UMA カード向け run config に書く `DS4_ASYNC_T` の値を指定します。engine は `STRATA_DSV41_ASYNC_T` を読みません。setup がこの変数を読み、生成した config の `env` に `DS4_ASYNC_T` を置き、server が engine 子プロセスへ渡します。

UMA カードを含む setup では既定で `DS4_ASYNC_T=4` を設定し、通常の非並列 window では `T` が 4 以下かどうかを async 判定に使います。setup のコメントと既存資料は、これを Strix Halo の verify window を同期実行にする設定として説明しています。離散 GPU の setup ではこの変数を参照せず、engine の既定値を使います（`setup.py:8376-8388,8743-8750`; `src/dsv41/ds4_model.cu:9565-9569`）。

## 値と判定

| `STRATA_DSV41_ASYNC_T` | setup が config に書く値 | 意味 |
|---|---|---|
| 未設定、または空文字 | `DS4_ASYNC_T=4`（UMA カードがある場合） | window size 4 以下だけが async 判定を通る |
| 文字列がちょうど `8` | setup は `DS4_ASYNC_T` を書かない | 既存の `DS4_ASYNC_T` が他に無ければ engine の既定値 8 |
| その他の非空文字列 | 文字列をそのまま `DS4_ASYNC_T` に設定 | engine が `atoi` で整数変換した値を上限として使う |
| UMA カードなし、またはカード一覧なし | 変数を読まず、config env は空 | setup はこの値を適用しない |

setup は空文字を `or "4"` で 4 に置き換え、文字列全体が厳密に `"8"` の場合だけ config env への追加を省きます。数値検証、範囲制限、無効値警告はありません。たとえば `"5tail"` は config にそのまま入り、engine の `atoi` は先頭の整数 `5` を読みます。非数値文字列や `"0"` は変換結果が 0 となり、正の window size では閾値を満たしません。負値もそのまま渡され、正の window size は閾値を満たしません。空白・符号・末尾文字は setup では検査されません（`setup.py:8385-8388`; `src/dsv41/ds4_model.cu:1136`）。

「8 で既定に戻す」は、config または親環境に別の `DS4_ASYNC_T` がない場合の動作です。setup の `carry_over()` は `DS4_ASYNC_T` を setup 管理変数として列挙していません。そのため、再 setup で新しい env が空になったとき、以前の run config にあった `DS4_ASYNC_T` は引き継がれ得ます（`setup.py:6502-6509,6525-6530,6648-6662`）。

## 有効になる条件

- setup 側では、カード一覧に `uma` が真のカードがある場合に限って対象変数を読みます。値を設定した setup は `DS4_ASYNC_T` を config に保存します（`setup.py:8385-8388,8743-8750`）。
- server はまず現在の環境をコピーし、その後 config の env を文字列化して上書きします。したがって、config の `DS4_ASYNC_T` は親プロセス環境の同名値より優先されます。setup が config に書かなかった場合は、親環境の `DS4_ASYNC_T` が engine に継承されます（`serve/server.py:3747-3763,9191-9194`）。
- engine は `DS4_ASYNC_T` を model state の初期化時に読み、未設定なら 8、設定されていれば `atoi` の結果を保持します。リクエストごとの再読み込みはありません（`src/dsv41/ds4_model.cu:1136`）。
- `async_max_t` は単独で async を有効にしません。非 Metal 経路では `DS4_SYNC` が設定されていると `sync_decode` が真になり、通常の window は同期です。Metal 分岐では `DS4_ASYNC` が未設定なら `sync_decode` が真です。いずれも設定有無を見ており、空文字でも「設定済み」です（`src/dsv41/ds4_model.cu:1126-1136`）。
- 通常の `plan_window()` は `par` が真なら `DS4_ASYNC_T` の閾値と `sync_decode` に関係なく async にします。`par` は `o.threads` または `tp > 1` で真になります。一方、draft verification の別経路は `!sync_decode && T <= async_max_t` で判定し、`par` による上書きはありません（`src/dsv41/ds4_model.cu:2223,7785-7789,9565-9569`）。

## 実行時の詳細

setup は生成する config の `env` に `{ "DS4_ASYNC_T": value }` を格納し、`write_setup_config()` で保存します。server の `child_env()` がその値を engine の環境へ渡します。setup 変数自体は engine 子プロセスにも通常の環境継承で残り得ますが、engine の対象コードが読むのは `DS4_ASYNC_T` です（`setup.py:8743-8750,8770`; `serve/server.py:3747-3763`; `src/dsv41/ds4_model.cu:1136`）。

engine は `DS4_ASYNC_T` を `atoi` で整数にし、通常の window について `T <= async_max_t` を判定します。window size は処理前に `1 <= T <= kWin` などの条件で絞られます。`DS4_ASYNC_T=4` かつ `!par && !sync_decode` なら T=1 の drafter window は閾値を満たし、T=6 の verify window は満たしません。判定に失敗した場合は async 用の mailbox sequence を設定せず、通常の同期経路になります（`src/dsv41/ds4_model.cu:7761-7767,7785-7792,9565-9569`）。

対象変数に対応する専用ログ、警告、終了コード分岐は見つかりませんでした。setup は値を検証せず config に書き、engine は整数化後に分岐へ使います。既存資料は Strix Halo の 128 GB 構成、2.00 bpw、greedy、256 token の 2026-10-25 測定として、code decode 15.87–16.33 から 20.14–21.28 tok/s、agent 15.93 から 18.48 tok/s を報告しています。これは資料に記載された測定結果であり、この調査で再測定した値ではありません（`docs/STRIX_HALO.md:79-84`; `docs/DEEPSEEK41.md:51-59`）。

## 根拠

- setup における候補変数の実読み取りと出力値の生成: `setup.py:8376-8388`。
- setup config への保存と既存 env の引き継ぎ: `setup.py:6502-6509,6525-6530,6648-6662,8743-8750,8770`。
- config env の engine 子プロセスへの適用: `serve/server.py:3747-3763,9191-9194`。
- engine が読む実名、既定値、数値変換、同期条件、window 判定: `src/dsv41/ds4_model.cu:1126-1136,7761-7792,9565-9569`。
- Strix Halo の条件説明と既存測定: `docs/STRIX_HALO.md:79-84`, `docs/DEEPSEEK41.md:51-59`。
