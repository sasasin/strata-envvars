# `STRATA_METAL_GEMV_NR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal decode window の GEMV カーネルで、複数 token をまとめて処理するときに各 lane が扱う出力行数（カーネル template の `NR`）を 1 から 2 にする実験用の選択値です。既定値は 1 で、環境変数を `2` と解釈した場合だけ条件付きで tile を変更します。GEMV の対象演算やモデル設定を切り替えるものではありません。実装は `Window::gemv` です（`engine/metal/src/engine/window.cpp:1019-1061`）。

## 値と判定

`std::getenv` で値の有無を調べ、設定されていれば `std::atoi` の戻り値を使います。文字列全体の検証はなく、`atoi` が先頭から読める整数を変換します。したがって未設定は 1、空文字は 0、`true` のような数字で始まらない文字列も 0 です。`2tail` や先頭空白付きの ` 2` は 2 と判定されます。変換結果がちょうど 2 でない値は tile 変更を起こしません。大文字小文字の扱いはありません（文字列比較ではないため）。読み取り式は `engine/metal/src/engine/window.cpp:1036-1045`。

| 条件 | unset | tile を変える値 | tile を変えない例 |
|---|---:|---|---|
| Metal `Window::gemv` の初回呼び出し時 | 1 | `2`, `02`, `+2`, `2tail`, ` 2`（`atoi` 結果が 2） | 空文字、`0`, `1`, `3`, `-2`, `true`, `0anything` |

`atoi` は変換不能な文字列を 0 として扱い、無効値の警告や fallback ログはありません。2 以外の変換結果は既定 tile のままです。数値変換後に上限・下限を clamp する処理はありません（同 `window.cpp:1039-1044`）。

## 有効になる条件

- Metal backend の `Window::gemv` が実行されること。Metal プロジェクトは macOS 専用で、`STRATA_METAL_ENGINE=OFF` の build では engine を作りません（`engine/metal/CMakeLists.txt:1-2,18-20,105-109,168-177`）。
- GEMV の token 数 `ntok` が 1 より大きく、出力行数 `n_out` が 2048 以上であること。この条件を外れる場合、値が 2 でも tile は変わりません（`engine/metal/src/engine/window.cpp:1039-1044`）。
- 通常の window `run` からは各 layer の GEMV と head GEMV が対象です。batch rows が一つの window にまとめられる経路も `run(S, ...)` を呼ぶため対象になり得ます（`engine/metal/src/engine/window.cpp:1153-1214,1614-1617,1644-1667`）。一方、batch slot を一つずつ処理する fallback は `run(1, ...)` を使うため、この条件を満たしません（同 `window.cpp:2255-2269`）。
- MTP draft model の GEMV は `Window::gemv` とは別の lambda で tile を作り、この値を読みません（`engine/metal/src/engine/window.cpp:2707-2725`）。CLI 引数や他の環境変数によるこの値の上書きはありません。

## 実行時の詳細

環境値は `Window::gemv` 内の関数ローカル `static const int` で初期化されるため、プロセス中の最初の同関数呼び出しで一度だけ読み取られます。その後に環境を変更しても反映されません（`engine/metal/src/engine/window.cpp:1039`）。

値が 2 で適用条件も満たす場合、初期 tile `(L, Rr, S, K)` のうち、`S=8,K=2` なら `S=4,K=2` にし、`S=8,K=1` なら `S=4` にします。さらに `K=1`、または `L=32,K=2` のとき `Rr=2` にします。それ以外の初期 tile はこの条件による変更を受けません。ここで `Rr` がカーネルの `NR` に対応し、結果として選ばれる `gemv_<type>_<L>_<Rr>_<S>_<K>` pipeline 名と grid の行 tile 幅が変わります（`engine/metal/src/engine/window.cpp:1021-1045,1048-1061`; template 引数 `NR` と lane ごとの行処理は `engine/metal/kernels/gemv.metal:24-45,60-76`）。

カーネルのコメントは NR の違いで加算順序を揃え、答えは変わらない設計意図を記しています（`engine/metal/src/engine/window.cpp:1037-1038`）。この調査ではその正確性を実行・測定していません。登録情報でも本変数は `research`、NR=2 は調整実験として記録され、製品採用の結論は付いていません（`terminal/data/settings-register.json:22371-22399`）。

## ログと測定値

環境変数の値や選ばれた NR を知らせる専用ログ、無効値の警告、変数固有の終了経路はありません。選択された関数名に対応する Metal function が見つからない場合、pipeline 取得時に stderr へ `mtl: no function <function> `（エラー詳細がある場合は続く）を出して exit code 3 で終了します（`engine/metal/src/engine/window.cpp:327-333,1048-1050`; `engine/metal/src/mtl_rt.mm:229-255`）。変数による速度差の測定値は、対象 commit の利用者向け資料から確認できません。

## 根拠

- `engine/metal/src/engine/window.cpp:1019-1061` — GEMV の既定 tile、値の読み取り、適用条件と dispatch 設定。
- `engine/metal/src/engine/window.cpp:1153-1214,1489-1492,1614-1617,1644-1667,2255-2269,2707-2725` — window / batch rows / fallback / MTP の呼び出し範囲。
- `engine/metal/kernels/gemv.metal:1-7,24-45,60-90,93-100` — GEMV template の NR、行処理、利用可能な kernel variants。
- `engine/metal/CMakeLists.txt:1-2,18-20,105-109,168-177` — Metal engine の build 条件。
- `engine/metal/src/mtl_rt.mm:229-255` — pipeline が見つからない場合の診断と終了。
- `terminal/data/settings-register.json:22371-22399` — 候補の登録情報と research 扱い。挙動の根拠には使用していません。
