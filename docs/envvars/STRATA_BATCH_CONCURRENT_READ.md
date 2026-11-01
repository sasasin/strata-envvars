# `STRATA_BATCH_CONCURRENT_READ`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

batch serving 中の prompt 読み取りを専用スレッドで進め、その間、既存 slot の batch window を実行します。これにより、新しい request の prompt 読み取りの間も、decode 中の slot が進みます。対象は Strata engine の batch prompt 経路です。候補名の直接参照は `src/program/generate.cpp` の読み取り 1 箇所のほか、説明コメントと `tools/par/recon3.py` の実験設定例にあります。後者は環境変数を設定する側であり、読み取り実装ではありません。

## 値と判定

値は `std::atoi` で整数に変換し、変換結果が 0 以外なら opt-in になります。文字列全体の検証やエラー報告はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（既定） |
| 空文字 | `atoi("") == 0` のため無効 |
| 数値として 0 になる文字列 | 無効。例: `0`, `0abc`, 数字より前に空白だけがある文字列 |
| 数値として 0 以外になる文字列 | 有効。例: `1`, `-1`, `2`, `1abc`, ` 1` |

したがって、真偽値の `true` や先頭文字だけが `1` かどうかでは判定されません。`atoi` が読み取れる先頭の整数部分を使い、整数部分の後の文字は判定を変えません。範囲外の数値文字列について、Strata は別途検査や fallback を実装していません。

読み取り結果は `read_part` 内の `static const bool` に保存され、最初に初期化された後は同一プロセス内で再評価されません。起動後に環境を書き換えても反映されません。CLI による同名設定や、別環境変数による優先上書きはありません。

## 有効になる条件

変数が有効でも、次の条件を満たすときだけ専用スレッド経路を使います。

- `--batch` または同義の `--slots` に正の slot 数が指定されている。
- `--no-prefill-borrow` が指定されている。
- batch slot が実際に decode 中である（`batch_on()`）。
- piped 経路ではなく、layer split ではない（`piped == false` かつ `stages.empty()`）。実装コメントはこの opt-in を one GPU の経路として説明している。コード上の直接条件は `stages.empty()` で、別個の `multi_gpu` 判定はありません。
- request に画像が含まれず、elastic K/V（`kvg.on`）も使われていない。
- batch prompt 分割 helper が正の piece size を返す。この設定の対象となる通常の単一 GPU batch 経路では prompt は chunk ごとに処理される。layer split では batch read helper が複数 chunk の piece を返す場合があるが、この変数の guard が layer split を除外する。

条件のどれかが欠けると `run_conc` は通常の `run(q, r)` にそのまま渡します。環境変数自体を明示設定したが条件を満たさない場合に、この変数専用の警告やエラーを出すコードはありません。この設定の読み取りや guard に OS ごとの分岐、backend ごとの分岐、この設定専用の build macro 判定はありません。処理は `src/program/generate.cpp` の GPU engine の batch serving 実装にあります。

## 実行時の詳細

専用スレッドで `run(q, r)` を呼び、main thread は読み取り完了まで、batch が続いていれば `batch_step()` を回します。読み取りスレッドはメイン session に prompt を読み、slot の window は各 slot の session を使います。`--no-prefill-borrow` が必要なのは、prompt が slot の expert cache を借りないためです。piece の終わりに slot 停止などの入力行を処理し、読了後に reader を `join()` します。

成功時、stderr に `strata batch: read N tokens on a thread of its own in X ms; the slots ran W windows meanwhile` が出ます。これはこの経路が使われた場合のログで、未設定時や条件不成立時には出ません。

読み取りスレッド内で例外が起きると `read_ok=false` とし、例外文を `the prompt read failed: ...`（未知の例外なら `the prompt read failed`）に設定します。batch window が失敗した場合は `a batch window failed` で batch を fatal 扱いにします。いずれも通常の prompt read エラー処理へ戻り、stderr に `strata serve: <理由>`、stdout に `ERR <理由>` を出して engine の request 処理を失敗させます。CUDA fault が検出される場合は同じエラー経路から process を即時終了する処理があります。

## 根拠

- `src/program/generate.cpp:15255-15263` — 変数の読み取り、`atoi` による判定、static cache。
- `src/program/generate.cpp:15264-15317` — 適用条件、reader thread、slot window の並行実行、成功ログ、失敗時の値。
- `src/program/generate.cpp:15701-15707` — prompt を piece に分けて `run_conc` に渡す呼び出し。
- `src/program/generate.cpp:15912-15932,15954-15965` — prompt read の呼び出し元と失敗時の stderr/stdout、CUDA fault 時の終了。
- `src/program/generate.cpp:3190-3197` — `--no-prefill-borrow` と `--batch` / `--slots` の CLI 設定。
- `include/strata/program/batch_read.hpp:22-28` — batch/piped/layer split/slot 状態ごとの prompt piece size。
- `docs/BATCHING.md:3-8` — `--batch` が複数 conversation を同時に decode する機能であること。
- `tools/par/recon3.py:22-23,41-42` — 実験設定での環境変数の設定例。実行時の読み取り箇所ではない。
