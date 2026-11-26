# `STRATA_DF_BRANCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP verifier の graph capture 内で、GDN mixer のゲート `a/b` と投影 `z`、および条件を満たす QSA 層の query 計算を、入力だけを読む並列 side stream に分ける opt-in スイッチ。main stream 上の K/V 投影や convolution などと重ねて graph に記録し、イベントで依存関係をつなぐ。使うのは `Verifier::record_window` の単独 window 経路であり、通常の逐次実行や出力値を選ぶ機能ではない（`engine/src/core/verify.cpp:1364-1375,1549-1552,1610-1617,1922-1929,1958-1960,2061-2075,2414,2578`）。

初期値は `false`。ただし verifier の CUDA/HIP 初期化時に値が有効なら、side stream 2 本と fork/join event を用意する。確保に失敗した場合はフラグを `false` に戻し、従来経路を使う（`engine/src/core/verify.cpp:1364-1375`）。

## 値と判定

`Verifier::init` 内で `std::getenv` し、未設定ポインタでないことと `std::atoi(v) != 0` の両方を判定する。文字列全体の妥当性確認や `true` / `false` の解釈はない。`atoi` が読む先頭の整数部分が 0 なら無効、非 0 なら有効となる。したがって空文字・数値に変換できない文字列は 0 扱い、`0anything` は無効、`1anything` と `-1` は有効。先頭の空白や符号を含む整数文字列も `atoi` の変換規則に従う。整数範囲外の入力の結果はこのコードで保証されない（`engine/src/core/verify.cpp:1367-1368`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP verifier の初期化 | 無効 | `1`、`-1`、`1anything` | 空文字、`0`、`0anything`、`true`、`abc` |
| Metal verifier | `Verifier::init` が Metal 分岐で先に return するため、この読み取りに到達しない | 該当なし | 該当なし |

CLI 引数による値の上書きはこの読み取り箇所にはない。Strata 内でこの変数を設定・転送する参照も確認できず、プロセス環境から直接読む（同名参照の全体検索結果では `verify.cpp` が唯一の実コード読み取り箇所）。

## 有効になる条件

- CUDA/HIP の verifier が初期化されること。Metal は `Verifier::init` の早期 return により読み取り・適用されない（`engine/src/core/verify.cpp:978-993,1367-1368`）。
- window が単一グループであること。`G` は split window または長い window を二分すると 2 になり、それ以外は 1（`engine/src/core/verify.cpp:1484-1486`）。
- batch capture (`batch_rec_`) でなく、`STRATA_VERIFY_PROFILE` が設定されておらず、`STRATA_SIDE_MIXER` が無効であること。`br` は `df_branch_ && G == 1 && !batch_rec_ && !prof_on_ && !side_mixer`（`engine/src/core/verify.cpp:1262,1503-1505,1610`）。
- `STRATA_SIDE_MIXER` が未設定の場合、HIP は `g_side_mixer()` の既定値 0。CUDA は device compute capability が 12.0 の場合に既定で mode 2、それ以外は 0。したがって CUDA 12.0 では別途 `STRATA_SIDE_MIXER=0` を指定しない限り、この変数の分岐は抑止される。明示値は 0..2 に clamp され、1 または 2 なら side mixer が優先される（`engine/src/core/verify.cpp:272-292,1610`）。
- 初期化時に stream/event の作成がすべて成功すること。失敗するとエラーをクリアして `df_branch_` を無効化し、通常の stream 経路に戻る（`engine/src/core/verify.cpp:1369-1375`）。
- GDN 層ではゲートと `z` の計算を枝分けする。QSA 層の query 側の枝分けはさらに `qb` が真の場合だけ行われる（`engine/src/core/verify.cpp:1922-1930,2061-2075`）。

ソースには OS による分岐はない。初期化コメントは Linux の open modules/GSP 環境で過去に graph が停止した報告を理由に既定 OFF と記すが、Windows だけを有効化する条件などは実装されていない（`engine/src/core/verify.cpp:1364-1366`）。

## 実行時の詳細

設定は各 `Verifier::init` の初期化中に読み取られ、インスタンスの `df_branch_` に保持される。実行中に環境を変更しても既存 verifier の値は再読込されない。値が有効なら、初期化中に `df_fork_` と2組の side stream/join event を作る（`engine/src/core/verify.cpp:956-966,1364-1375`）。

`capture` は window の graph を初回に記録し、既に同じ graph executable があれば再 capture しない。`record_window` は `br` の条件を計算し、fork event を main stream に記録して side stream を待たせ、side stream の処理後に join event を記録して main stream を待たせる（`engine/src/core/verify.cpp:1610-1617,3254-3289`）。

GDN 層では `a/b` と `z` をそれぞれ side stream 0/1 で qkv projection と convolution に並行して投入し、再帰計算の前に両方を join する（`engine/src/core/verify.cpp:1922-1930,1958-1960`）。QSA 層では `qb` の場合、Q query の projection・norm/RoPE等を side 0、indexer query を side 1 で処理し、block score 前に indexer query、attention 前に query を join する（`engine/src/core/verify.cpp:2061-2075,2414,2578`）。同じ計算処理を異なる stream 順序で graph に記録する実装であり、分岐条件が満たされない場合は既定の main stream 経路を通る。

## ログと測定値

`STRATA_DF_BRANCH` 固有の有効・無効ログや確保失敗の警告はない。初期化時の side stream/event 作成失敗では `df_branch_` を false に戻して継続する（`engine/src/core/verify.cpp:1369-1375`）。dispatch 記録が有効なら、window の note に `win df_branch=%ld sh_stream=%ld prof=%ld`、GDN 層に `gdn layer: side_gates=%ld side_proj=%ld df_branch=%ld` が記録される。実際に window で使う値は後者の `br` 条件付き値であり、前者は同じ適用条件をそのまま表す。dispatch note は `STRATA_DISPATCH_STATS=0` で抑止される（`engine/src/core/verify.cpp:1545-1548,1932`; `engine/include/strata/core/dispatch_stats.hpp:114-119,145-152`）。

調査対象の `docs/DETAILS.md` にこの変数の測定値は見つからなかったため、速度・正確性の数値は記載しない。

## 根拠

- `engine/src/core/verify.cpp:1364-1375` — 環境読み取り、初期値判定、stream/event 確保と失敗時の fallback。
- `engine/src/core/verify.cpp:1262,1484-1486,1503-1505,1610-1617` — profiler・window 分割・side mixer による適用条件と fork/join。
- `engine/src/core/verify.cpp:1922-1930,1958-1960,2061-2075,2414,2578` — GDN/QSA の実際の並列処理と join。
- `engine/src/core/verify.cpp:3254-3289` — window graph の capture と再利用。
- `engine/include/strata/core/verify.hpp:677-682` — verifier に保持する flag・stream・event。
- `engine/src/core/verify.cpp:272-292` — `STRATA_SIDE_MIXER` の mode と CUDA/HIP の既定値。
