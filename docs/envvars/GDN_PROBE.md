# `GDN_PROBE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`GDN_PROBE` は Metal の `gdn_prompt_parity` ベンチで GDN scan の計算を意図的に省略する診断用フックであり、Strata の通常推論設定ではない。`engine/metal/tests/gdn_prompt_parity.cpp` が `--bench` 経路で値を Metal function constant 6 に渡し、`gdn_prompt.metal` の `gdn_scan_r` が値 1 で simdgroup 間の部分和交換を、値 2 で状態更新を省略する。カーネルコメントは値 1 を誤結果になる設定と明記している。既定値 0 ではこれらの省略分岐に入らない（`engine/metal/tests/gdn_prompt_parity.cpp:211-243`; `engine/metal/kernels/gdn_prompt.metal:162-164,217-239`）。

この読み取りは `engine/metal/tests/gdn_prompt_parity.cpp` に限られ、`engine/metal/CMakeLists.txt` では `tests/*.cpp` を個別の実行ファイルとして列挙する。通常の `strata` 実行ターゲットには同ファイルが含まれず、通常の Metal エンジン側にも `GDN_PROBE` の読み取りはない（`engine/metal/CMakeLists.txt:29-42,108-110`）。

## 値と判定

ベンチの後半で `cb < 0 && nm[9] != 'v'` のときだけ `getenv("GDN_PROBE")` を調べ、未設定なら 0、設定ありなら `std::atoi` の結果を function constant 6 に渡す。空文字、数値に変換できない先頭文字列は `atoi` により 0 になる。`atoi` は先頭空白と符号を許し、数字列の後ろの文字列は変換を止めるだけなので、たとえば `"  -2tail"` は -2、`"1x"` は 1、`"0anything"` は 0 になる。文字列全体の検証、大文字小文字の比較、値域 clamp はない。変換可能な整数範囲を超えた場合の `atoi` の動作はここでは規定されない（`engine/metal/tests/gdn_prompt_parity.cpp:228-233`）。

| 条件 | unset | 有効になる値（例） | 無効・特別な値（例） |
|---|---|---|---|
| macOS Metal の `gdn_prompt_parity --bench` が `gdn_scanr_4` を測る経路 | function constant 6 に 0 を渡す | `1`, `2`, `-1`, `1tail`（整数変換値がカーネルの分岐値と一致したときだけ省略分岐を有効化） | 空文字、`true`、`abc` は 0。`0`, `0anything`, `3`, `4` もこの scan カーネルでは省略分岐を有効化しない |
| 通常の parity 実行、`--stress`、`strata` 本体 | 読み取りなし | 該当なし | 環境変数はこの経路に作用しない |

値 1 は各 token の simdgroup 部分和交換を飛ばし、値 2 は状態更新ループを飛ばす。どちらも `gdn_scan_r` の計算を変える診断値で、通常の正しい scan を指定する値ではない。値 3・4 は別の chunked カーネル `gdn_cprep2` / `gdn_cstate2` にある分岐でのみ使われ、このベンチが値を渡す `gdn_scanr_4` の `gdn_scan_r` には対応する分岐がない（`engine/metal/kernels/gdn_prompt.metal:217-234,640-654,720-788`）。

## 有効になる条件

- macOS 上でビルドされた Metal parity/benchmark 実行ファイル `gdn_prompt_parity` を起動すること。Metal CMake は `tests/*.cpp` を個別実行ファイルにする（`engine/metal/CMakeLists.txt:29-42`）。
- 最初の CLI 引数が `--bench` であること。通常 parity 経路は `!bench` の比較を行い、その後 return するため環境値を読み取らない。`--stress` は別分岐で先に return する（`engine/metal/tests/gdn_prompt_parity.cpp:24-28,100-162,163-210`）。
- ベンチの scan ループで `gdn_scanr_4` を選ぶ反復であること。この pipeline に function constant 6 が設定される（`engine/metal/tests/gdn_prompt_parity.cpp:228-240`）。
- 他の環境変数、モデル状態、サーバーモード、CLI の追加引数による優先・上書きはない。`--bench` の後続引数はこのコードでは参照されない。

## 実行時の詳細

値は起動時に一括 cache されず、ベンチのループ内で各該当反復の pipeline を作る直前に読み取られる。実際には設定有無の `getenv` と `atoi` 用の `getenv` がそれぞれ呼ばれる。function constant はその pipeline 作成時に設定され、その pipeline の実行に使われる。プロセス実行中の環境変更を反映する仕組みや、子プロセスへの転送はない（`engine/metal/tests/gdn_prompt_parity.cpp:221-240`; function constant の整数設定は `engine/metal/src/mtl_rt.h:39-46`）。

`gdn_scanr_4` の反復では `cb=-4` であり、`nm[9] != 'v'` が成立するため変数が読み取られる。ループには `"chunked"` も含まれ、同じ条件式の `nm[9]` はその文字列の終端を越える添字になる。ただし chunked の dispatch 組み立ては scan pipeline を使わず、`cb == -100` 分岐で別の `gdn_cprep` / `gdn_cstate` / `gdn_cout` pipeline を追加する（`engine/metal/tests/gdn_prompt_parity.cpp:61-76,228-240`）。そのため chunked の計算に `GDN_PROBE` が適用されるとはこのコードから言えず、終端外添字を含む条件の評価結果も保証できない。

## ログと測定値

この変数の値や有効化理由を示すログはない。ベンチは通常どおり `T 2048, ...` の scan / pre / post 時間を stdout に出すが、値 1 または 2 では scan の計算内容が変わるため、その時間や出力を正しい GDN scan の測定値として扱えない。ベンチ経路は parity 比較を実施せず、最後は 0 を返すため、これらの値でも省略処理を失敗として報告しない（`engine/metal/tests/gdn_prompt_parity.cpp:202-210,221-243`; `engine/metal/kernels/gdn_prompt.metal:217-234`）。`docs/DETAILS.md` に `GDN_PROBE` の測定値や利用説明は見つからなかった。

## 根拠

- `engine/metal/tests/gdn_prompt_parity.cpp:24-28,100-162,163-210,211-243` — CLI 分岐、読み取り、function constant 設定、benchmark 実行。
- `engine/metal/kernels/gdn_prompt.metal:162-164,217-239` — function constant 既定値と `gdn_scan_r` の省略処理。
- `engine/metal/kernels/gdn_prompt.metal:640-654,720-788` — 値 1・2・3・4 の別 chunked kernel での使用。
- `engine/metal/src/mtl_rt.h:39-46` — `Constants::i` の整数 function constant 設定。
- `engine/metal/CMakeLists.txt:29-42,108-110` — test ソースの実行ファイル化と `strata` 本体ターゲット。
