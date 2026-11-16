# `STRATA_SERVE_STOP_SKIP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

serve エンジンが STOP を検出したとき、実行中の decode window 全体を捨てて会話状態を直前の commit 位置に保つ処理を有効にする。既定で有効で、値が厳密に `0` の場合に無効になる。これは生成内容の選択を変える設定ではなく、STOP 後にクライアントへ送られない window をセッションへ commit するかどうかを制御する。通常の逐次経路と pipeline 経路の両方で参照される（`src/program/generate.cpp:19509-19515,20080-20099,20647-20654`）。

## 値と判定

`generate.cpp` の関数内 `static const bool` 初期化で `std::getenv` の戻り値を helper に渡す。helper は null（未設定）なら有効、設定されていれば `strcmp(value, "0") != 0` で判定する。従って文字列全体が厳密に `0` のときだけ無効であり、数値変換や真偽値の parse、空白除去、大文字小文字変換はない（`src/program/generate.cpp:19513-19515`、`include/strata/core/serve_stop_bound.hpp:78-80`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値 |
|---|---|---|---|
| serve decode の共通判定 | 有効 | 空文字、`1`、`00`、`false`、` 0`、`0 ` | 厳密に `0` |

空文字は「設定あり」でも有効。`0anything` も文字列全体が `0` ではないため有効。無効な文字列としての拒否や fallback はない。CLI 引数・設定ファイル・別の環境変数による上書き分岐はこの判定箇所にはない（`include/strata/core/serve_stop_bound.hpp:78-80`）。

## 有効になる条件

値判定が有効でも、以下をすべて満たすときだけ window を捨てる。

- serve 中に STOP フラグが立っている。serve の stdin reader は `STOP` 行を `stop_req` に反映し、処理中の request がそのフラグを確認する（`src/program/generate.cpp:14825-14838,14874-14879`）。
- 対象が request の最初の window ではなく、prompt 行を含む merged window でもない。
- その window の commit がまだ取り消し可能（`commit_deferred()` が true）。すでに状態を進めた one-token path は対象外。

通常経路では上記を `serve_skip_stopped_window` が判定する。pipeline 経路では `A.seq > 0` を確認し、全 verifier stage の commit が deferred の場合に同じ判定を通す（`include/strata/core/serve_stop_bound.hpp:67-79`、`src/program/generate.cpp:20080-20099,20647-20654`）。request が上限または EOS で終わり STOP が立っていない場合、この処理は発火しない（`src/program/generate.cpp:20107-20122,20847-20849`）。

ソースの分岐に OS/backend/macro 別の値判定はない。設定レジストリは当該読み取りを `cuda-hip` と分類している。実行にはこの serve decode 実装を含むビルドが必要（`data/settings-register.json:36367-36378`）。

## 実行時の詳細

値は request ごとに再評価せず、`generate.cpp` 内の関数ローカル `static` として、制御が初めて該当宣言へ到達したときに一度だけ読み取る。以後プロセス内で環境を変更しても反映されない（`src/program/generate.cpp:19513-19515`）。

対象 window を捨てると、その window の commit と token 出力を行わず、request の finish を `cancel` にする。pipeline 経路で次の window B が A の状態を先行して commit 済みなら、A 前の snapshot へ戻すための undo を設定し、保持行数 `undo_keep` を 0 にする（`src/program/generate.cpp:20080-20099`）。通常経路は commit 前に loop を抜ける（`src/program/generate.cpp:20647-20654`）。serve の終了処理は直前までの `consumed` を live session とし、`DONE` 行には生成数・finish などを出力するため、捨てた window の token は session にもクライアント出力にも加わらない（`src/program/generate.cpp:20100-20116,20847-20849,21023-21028,21176-21200`）。

## ログと測定値

この変数専用の警告・ログ出力はない。捨てた request は serve プロトコルの `DONE` 行で finish が `cancel` になる。`DONE` は標準出力に出る（`src/program/generate.cpp:20086-20088,20650-20653,21176-21200`）。`docs/DETAILS.md` に本変数の挙動や測定値の記載は見つからなかったため、性能・精度への定量的な主張は記載しない。

## 根拠

- `src/program/generate.cpp:14825-14838,14874-14879` — STOP 入力と共有フラグ。
- `src/program/generate.cpp:19509-19515` — 値の読み取りと static cache。
- `src/program/generate.cpp:20080-20099,20647-20654` — pipeline / 通常経路での skip 判定と処理。
- `include/strata/core/serve_stop_bound.hpp:67-80` — 適用条件と値の判定。
- `src/program/generate.cpp:21023-21038,21176-21200` — session 維持と DONE 出力。
