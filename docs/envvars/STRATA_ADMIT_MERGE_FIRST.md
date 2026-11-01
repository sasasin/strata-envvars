# `STRATA_ADMIT_MERGE_FIRST`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。外部ライブラリの環境変数は対象外。

## 役割

continuous batching の batch admission で、prompt の末尾部分と最初の生成 token を同じ verify window にまとめます。通常は prompt の最後の token を含む window を先に読み、その後、最後の token から最初の生成 token を作る decode window を実行します。この変数が有効で条件を満たすと、prompt の末尾最大 `max_t` token を最初の decode window に持ち越し、最初の生成 token まで一度に処理します。適用先は `src/program/generate.cpp` の serve loop にある batch admission 経路です。通常の単独生成や batch slot の後続 decode window を切り替える変数ではありません（`src/program/generate.cpp:15890-15910,16014-16021,16737-16762`）。

## 値と判定

値は数値や真偽値として parse せず、環境変数の先頭文字だけで判定します（`src/program/generate.cpp:294-300`）。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | ON（設定値の先頭が終端文字 `\0` で、`'0'` ではないため） |
| 先頭文字が `0` | OFF（例: `0`, `0abc`） |
| それ以外 | ON（例: `1`, `true`, `false`, `2`, 空白で始まる値） |

大文字小文字、文字列全体、後続文字、数値としての妥当性は検査されません。CLI 引数や設定ファイルからこの判定値を上書きする処理はありません。環境変数を読むのは `admit_merge_first_env()` 内の関数ローカル `static const bool` 初期化時で、最初にその関数が呼ばれた値をプロセス内に保持します。起動時の一括読み取りではなく、最初の候補 window で遅延評価されます。その後の環境変更は再評価されません（`src/program/generate.cpp:294-300,15912-15928`）。

## 有効になる条件

値が ON でも、`merge_from()` が次の条件をすべて満たす場合だけ merge 位置を返します。条件を満たさない場合は `merge_at` が `-1` のままとなり、通常の prompt window と初回 decode window に戻ります（`src/program/generate.cpp:15895-15910`）。

- batch admission 中である（`admit_slot >= 0`）。通常の `GEN` は対象外。serve loop は `BGEN` / `BGENI` を admission 用の `GEN 1` / `GENI 1` に変換します（`src/program/generate.cpp:13565-13583`）。
- 今回の `max_new` がちょうど `1` で、batch MTP と pipelined request のどちらも使っていない。
- 対象が最終 prompt 区間（`to == n - 1`）で、turn/root/message/pin checkpoint の境界と重ならない。
- 画像入力、K/V graph、peer device、remote cache / remote expert、filesystem swap がない。
- `STRATA_LOGPOS` が未設定である。値が空でも設定されていれば対象外。
- `host_res` が空でなく、pending swap がなく、全 expert の residency index が非負である。加えて、各 pipeline stage の verifier で resident graph が live であり、使用可能な `max_t` の最小値が 2 以上である。

`max_t` は kernel の `kVerifyMaxT` と各 stage verifier の `max_t()` の最小値で、merge 位置は `max(a0, n - max_t)` です。したがって最後の prompt token は必ず最初の window に入り、余裕があればその前の最大 `max_t - 1` token も同じ window に入ります（`src/program/generate.cpp:15904-15910`）。

この実装箇所に OS や backend ごとの値判定分岐はありません。適用可否は上記の serve / verifier / resident-state 条件で決まります。

## 実行時の詳細

serve loop は prompt の各区間について `windows_ok()` を調べます。window 経路なら `merge_from()` に候補位置を問い合わせ、prompt 読み取りの終点を merge 位置までに短縮します。残した末尾 token は、次の最初の decode window に入ります。merge を使わない場合は従来どおり prompt を `n - 1` まで読み、最初の verify window に最後の prompt token だけを使います（`src/program/generate.cpp:15912-15932,16012-16021`）。

最初の window は `merge_at` からの prompt token を `window` に入れ、`T` を `merge_T` にします。最初の出力 token を含む window を実行し、後続の通常 window は従来の `T` 決定に戻ります（`src/program/generate.cpp:16737-16762,16800-16803`）。この実装は入出力の読み方と window の組み方を変えます。`docs/BATCHING.md` も「admission reads its last prompt tokens and its first token in one window」と説明しています（`docs/BATCHING.md:110-120`）。

## ログと失敗経路

merge の条件が不足しても警告やエラーは出ず、標準の window 分割にフォールバックします。`STRATA_TRACE` が設定されている場合、stderr に通常の prompt read 行と、merge が選ばれたときは `strata trace: the first window takes the last %lld prompt tokens` が出ます（`src/program/generate.cpp:12155-12164,15934-15942`）。merge 成功時、prompt 区間の処理完了として stdout に通常の `PP ...` 行も出ます（`src/program/generate.cpp:15948-15952`）。

読み取りや verify 自体が失敗したときは、この変数専用のエラー処理ではなく prompt 経路の通常処理に進みます。たとえば `read_windows()` の失敗は stderr と stdout の `ERR ...` を出し、条件により request を終了します（`src/program/generate.cpp:15954-15965,14893-14920`）。

## 根拠

- 読み取り・parse・cache: `src/program/generate.cpp:294-300`。
- batch admission の識別と `GEN 1` への変換: `src/program/generate.cpp:13565-13583`。
- merge の適用条件と位置: `src/program/generate.cpp:15890-15910`。
- prompt 区間の短縮、trace、通常の `PP` 出力: `src/program/generate.cpp:15912-15952`。
- 最初の verify window の位置と token 数: `src/program/generate.cpp:16014-16021,16737-16762,16800-16803`。
- resident graph の判定: `include/strata/core/verify.hpp:192-195`。
- 既存説明との照合: `docs/BATCHING.md:110-120`。
