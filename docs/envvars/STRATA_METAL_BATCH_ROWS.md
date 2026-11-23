# `STRATA_METAL_BATCH_ROWS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal エンジンのバッチ行を、1 回の複数行 window として処理するか、各行を 1 token ずつ順番に処理するかを選びます。未設定時および値が文字列 `0` と完全一致しないときは、複数行経路を選びます。値が `0` のときは逐次経路を選びます。ただし複数行経路には、バッチ用状態バッファが確保されていることも必要です。読み取りと分岐は Metal の `Window::run_slots` にあります（`engine/metal/src/engine/window.cpp:2255-2271`）。

これは `--batch` スロットの Metal 処理に関する切替です。Metal 以外の backend の処理にはこの読み取り箇所はありません。Metal では生成処理が CLI の `o.batch` を `set_batch_slots` に渡します（`engine/src/program/generate.cpp:5310-5313`）。

## 値と判定

`std::getenv` で設定有無を確認し、設定されていれば値全体を `std::string` にして `"0"` と完全一致するか比較します。数値変換や trim、大文字小文字変換はありません。空文字は設定済みですが `"0"` ではないため、複数行経路を選びます（`engine/metal/src/engine/window.cpp:2257-2258`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Metal の `Window::run_slots` でバッチ用状態バッファが使える場合 | 複数行経路 | `0`（逐次経路を選択） | 空文字、`1`、`true`、`false`、`00`、`0anything`、` 0`（いずれも複数行経路） |
| Metal の `Window::run_slots` でバッチ用状態バッファが使えない場合 | 逐次経路 | `0`（逐次経路を選択） | 空文字、`1`、`true`、`false`、`00`、`0anything`、` 0`（いずれも複数行経路を要求する値だが、バッファ条件を満たさないため逐次経路） |

ここで「有効」は設定によって逐次経路を選ぶ意味です。`0` 以外の文字列を bool や整数として解釈する仕様ではありません。`one_window` は関数内 `static const` なので、スロットが存在して `run_slots` の判定箇所まで実行が進んだ最初の時点で値を読み、その判定をプロセス内で保持します。スロットが空の場合はその前に戻るため読み取りません。その後の環境変更は反映されません（同上）。

## 有効になる条件

- `STRATA_GPU_METAL` を定義した生成コードで、Metal エンジンのバッチスロット処理を通る必要があります。生成側は `o.batch` を `set_batch_slots` に設定します（`engine/src/program/generate.cpp:5310-5313`）。
- `set_batch_slots` は正の値を最大 8 に制限し、非正値ならスロット容量を 0 にします。window 初期化時には実際のスロット数と容量を比べ、容量を超えるスロットがあると `bigs_ok_` を false にして逐次処理にします（`engine/metal/src/engine/window.cpp:819-831,2215-2227,3591`）。
- `STRATA_METAL_BATCH_ROWS=0` は `one_window` を false にします。その他の値は複数行経路を選びますが、`bigs_ok_` が false なら値にかかわらず逐次経路です（`engine/metal/src/engine/window.cpp:2255-2268`）。
- `--batch` が指定されずスロットが作られない場合、`run_slots` は `metal window: no batch slots` で失敗します。環境変数はこの前提を作りません（同 `:2255-2256`）。

## 実行時の詳細

複数行経路では set 0 を active にし、`run_rows(rows, S, ...)` にまとめて渡します。`run_rows` は行数が 1 以上かつ `MAXT` と `max_t_` 以下であることを検査し、slot の範囲外や同じ window 内で重複する slot をエラーにします。モデルで M-RoPE が有効なのに slot 用テーブルがなければ、この経路は `metal window: batch rows without the slots' M-RoPE tables` で失敗します（`engine/metal/src/engine/window.cpp:1644-1667,2258-2260`）。`MAXT` は 8 です（同 `:127`）。

逐次経路では各行について slot を active にし、`run(1, ...)` と `commit(1, ...)` を実行してから次の行へ進みます。失敗時はループを止め、最後に set 0 を active に戻します（`engine/metal/src/engine/window.cpp:2262-2271`）。Verifier は Metal では各行が slot の状態で実行・commit されるとし、この関数へ処理を渡します（`engine/src/core/verify.cpp:5370-5379`）。

設定は `run_slots` 内の static 初期化で一度だけ評価されます（スロットが空なら初期化行に到達しません）。CLI の `--batch` はスロット数とバッファ条件を決めますが、`STRATA_METAL_BATCH_ROWS` の値を上書きする読み取りや優先順位分岐はありません（`engine/src/program/generate.cpp:5310-5313`; `engine/metal/src/engine/window.cpp:819-831,2255-2258,3591`）。

## ログと測定値

この変数の値を示す専用ログや警告はありません。スロット初期化時には stderr に `strata metal: %zu batch slots, each with its own running state and K/V (%.2f GB each, %.2f GB in all)` が出ますが、経路選択の表示ではありません（`engine/metal/src/engine/window.cpp:2242-2244`）。各経路の実行エラーは `err` に設定され、上位の verifier が失敗として返します。文書 `docs/DETAILS.md` に本変数の説明や測定値は見当たりません。

## 根拠

- 候補名の全参照は `engine/metal/src/engine/window.cpp:2257` のみです。`terminal/data/settings-register.json:20421` にも名前がありますが、これは登録データであり環境値の読み取りではありません。
- 読み取りと経路分岐: `engine/metal/src/engine/window.cpp:2255-2271`
- バッチバッファ、slot 数による逐次 fallback: `engine/metal/src/engine/window.cpp:819-831,2215-2244,3591`
- Metal 生成コードから CLI 値を渡す箇所: `engine/src/program/generate.cpp:5310-5313`
- Metal verifier からの呼び出し: `engine/src/core/verify.cpp:5370-5379`
