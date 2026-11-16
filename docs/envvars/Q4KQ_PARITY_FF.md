# `Q4KQ_PARITY_FF`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`native_expert_parity` 診断プログラムで使う expert の FF（中間幅）を、既定の `640` から上書きします。Strata の生成・推論・サーバー設定ではなく、この parity 診断の配列寸法、重みの行配置、CPU/GPU 計算寸法を変える値です。CUDA/HIP 版と SYCL 版の両方に読み取りがあります。`src/kernels/native_expert_parity.cpp:63,903-910`、`sycl/src/kernels/native_expert_parity.cpp:87-90`。

## 値と判定

どちらの実装も `main` 内で `std::getenv("Q4KQ_PARITY_FF")` を一度呼び、未設定なら初期値 `FF = 640` のまま、設定されていれば `std::atoll` の戻り値を `FF` に代入します。空文字も「設定あり」と判定され、`atoll("")` 相当の `0` になります。`atoll` は10進整数の先頭部分を読むため、先頭空白と符号を許し、数字の後ろは読みません（例: `"+1024tail"` は `1024`、`"tail"` は `0`）。全体一致や範囲チェックはありません。範囲外の値についてコードは検査・fallback を設けていません。`src/kernels/native_expert_parity.cpp:909-910`、`sycl/src/kernels/native_expert_parity.cpp:88-90`。

| ビルド | unset | 設定時に使われる値 | 値の検証 |
|---|---:|---|---|
| CUDA/HIP の `native_expert_parity` | 640 | `atoll` が変換した `int64_t` 値 | `native_fmt` は重み形式・活性値形式に対するブロック寸法の割り切れを検査するが、正数かどうかは検査しない。形式に適合しない寸法は `native_expert_parity` が理由を表示してその層／組を失敗扱いにする。 |
| SYCL の `native_expert_parity` | 640 | 同上 | 同じ `native_fmt` の寸法検査を通るか、また `native_expert_supported` が対応する組かを確認する。 |

したがって `1024` は変換値として使われますが、任意の整数が有効な expert 幅になるわけではありません。`0`、負数、変換できない文字列も読み取り時点では拒否されません。`native_fmt` のブロック検査を通った後の全ての異常寸法について、実行結果を保証する追加の FF 範囲検査は確認できません。`src/kernels/cpu/native_expert.cpp:262-310`。

## 有効になる条件

- 診断実行ファイルがビルドされている必要があります。CUDA/HIP ソースのターゲットは `STRATA_ENABLE_CUDA OR STRATA_ENABLE_HIP` のとき定義されます（`CMakeLists.txt:645-649`）。SYCL ターゲットは `STRATA_NATIVE_EXPERTS` のとき定義されます（`sycl/CMakeLists.txt:503-508`）。
- CUDA/HIP 版では `--synthetic`、`--synthetic-hadamard`、または GGUF の expert 層比較で、変換後の `FF` が `native_fmt` に渡されます（`src/kernels/native_expert_parity.cpp:945-985,988-1012`）。SYCL 版では `--synthetic` と実 GGUF 比較がその寸法を使います（`sycl/src/kernels/native_expert_parity.cpp:93-124`）。
- 値は診断プログラムの引数・モデル設定で再度上書きされません。実 GGUF を比較するときは、指定幅が読み込む gate/up/down tensor の形状に合っている必要があります。コードは指定された `FF` で `NativeFmt` を作り、その寸法に基づいて tensor データから blob をコピーします（`src/kernels/native_expert_parity.cpp:998-1012`）。
- `--load-check`、`--gguf-ple`、`--q5_1-min`、`--bf16-embd` はこの `FF` を expert 寸法として使いません。CUDA/HIP 版の `--gguf-embd` も `FF` は使いません（`src/kernels/native_expert_parity.cpp:934-944,752-800`）。この変数を読む処理はサーバー／通常の CLI 推論経路にはありません。

## 実行時の詳細

値は各 `main` の開始時にローカル／グローバル既定値を上書きし、その後の診断処理で使われます。プロセス内での再読み取り、static cache、リクエスト単位の評価はありません。したがって実行開始後の環境変更は反映されません。値の子プロセスへの転送もこの診断コードにはありません。`src/kernels/native_expert_parity.cpp:903-910`、`sycl/src/kernels/native_expert_parity.cpp:74-92`。

FF は gate/up の各行数、中間活性の長さ、down 行の入力幅、および関連する CPU/GPU scratch/output 計算に使われます。例えば CUDA/HIP 版では参照行列の割当と計算、`native_fmt`、kernel 寸法、合成 blob の生成に渡されます（`src/kernels/native_expert_parity.cpp:72-77,94-104,948-985`）。SYCL 版でも同様に `native_fmt`、合成 blob、参照計算、grouped GPU 計算へ渡されます（`sycl/src/kernels/native_expert_parity.cpp:102-108,129-150,281-328`）。

## ログと測定値

読み取り値そのものを出すログや、この変数専用の警告はありません。`native_fmt` が寸法のブロック整合性を拒否した場合、CUDA/HIP 版は合成モードで `<pair 引数>: native experts: expert geometry is not whole blocks`、実モデル比較で `layer N: native experts: expert geometry is not whole blocks` の形を表示します。SYCL 版も合成時は `<pair 引数>: ...`、実モデル比較では `layer N: ...` の形です。失敗数は最後に `native_expert_parity: N failures` と表示され、非ゼロなら終了コード `1` です（`src/kernels/native_expert_parity.cpp:971-975,1003-1016`、`sycl/src/kernels/native_expert_parity.cpp:102-106,354-360`）。測定値はこの環境変数について記載されたものを確認できません。

## 根拠

- `src/kernels/native_expert_parity.cpp:63,903-910` — 既定値と CUDA/HIP 版の読み取り。
- `sycl/src/kernels/native_expert_parity.cpp:87-90` — SYCL 版の既定値と読み取り。
- `src/kernels/cpu/native_expert.cpp:262-310` — expert 寸法の形式・ブロック検査と FF の保存。
- `CMakeLists.txt:645-649`、`sycl/CMakeLists.txt:503-508` — 診断ターゲットが定義される build 条件。
- `src/kernels/native_expert_parity.cpp:945-1016`、`sycl/src/kernels/native_expert_parity.cpp:93-124,354-360` — 値の利用箇所、無効な組の表示、終了結果。
