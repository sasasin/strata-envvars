# `COMMIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`COMMIT` は Strata の実行時設定ではなく、特定の engine package build script がソース revision を build ID や package metadata に記録するために読む環境変数である。確認できた読み取り元は Linux ARM64 CUDA、Windows CUDA、Linux SYCL、Linux HIP の packaging script で、他の実行経路で engine の動作を切り替える読み取りは見つからなかった。

- ARM64 CUDA では build ID の末尾 12 文字に使う（`tools/packaging/build_cuda_linux_aarch64.sh:20-28,36-41`）。
- Windows CUDA では `BUILD.json` の commit 欄と package build ID に先頭 12 文字を使う（`tools/packaging/build_cuda_windows.py:135-142,167-168,186-196`）。
- Linux SYCL では package build ID の先頭に使う（`tools/packaging/build_sycl_linux.sh:53-55,71-75`）。
- Linux HIP では status、`BUILD.json` の source、package build ID に使い、tarball checkout で `BUILD_ID` がまだない場合は先頭 9 文字を書き込む（`tools/packaging/build_hip_linux.sh:31,48-57,86-90,131-136`）。

## 値と判定

| ビルド | unset / 空文字 | 設定時に使われる値と検査 |
|---|---|---|
| Linux ARM64 CUDA | `${COMMIT:-...}` のため unset と空文字は同じ。`git rev-parse HEAD` に fallback し、失敗または空なら stderr に `build_cuda_linux_aarch64.sh: set COMMIT=<hex> (no .git here)` を出して exit 2。 | 非空の値は文字種・長さ・SHA 形式を検査せず採用。build ID にその先頭 12 文字を使用する。例: `abc`, `A B`, 40 桁以外もこの箇所では拒否されない。 |
| Windows CUDA | Python の `os.environ.get("COMMIT", "")`。unset と空文字は同じで、`git -C <src> rev-parse HEAD` の成功した stdout に fallback。 | 全体が小文字の 16 進文字列 12〜40 桁のときだけ受理（`[0-9a-f]{12,40}`）。大文字、空白、短すぎ・長すぎ、その他の文字は拒否。無効な非空値も git fallback せず `build_cuda_windows.py: set COMMIT=<hex> (no git commit found here)` で失敗する。 |
| Linux SYCL | `${COMMIT:-...}` のため unset と空文字は同じ。`git rev-parse --short=12 HEAD` に fallback し、失敗時は文字列 `unknown`。 | 非空の値は形式検査なしで採用し、`${commit}-oneapi${iccver}` の形で build ID に含める。 |
| Linux HIP | `${COMMIT:-unknown}` のため unset と空文字は `unknown`。 | 非空の値は形式検査なしで採用。先頭 9 文字や値全体を build metadata に使う。 |

この変数を読む箇所には数値変換、大文字小文字の正規化、trim、無効値からの一般的 fallback はない。Windows CUDA だけが値全体に形式検査を行う。各判定は build script の実行時に行われ、engine runtime のキャッシュや実行中の再読込には該当しない（上記各 script の読み取り行を参照）。

## 有効になる条件

- ARM64 CUDA script は Linux `aarch64` / `arm64` 以外では、`COMMIT` の読み取りより前に `build_cuda_linux_aarch64.sh:20-23` の OS/architecture check で exit 2 する。値が有効でも、そのほかの build prerequisites が満たされなければ package 作成まで到達しない。
- Windows CUDA script は Windows 上で `cuda12` または `cuda13` variant を引数に取る経路でだけ進み、それ以外は先に失敗する（`build_cuda_windows.py:151-158`）。有効な `COMMIT` は variant build 後に metadata/package ID に反映される。
- Linux SYCL script は Linux x86_64 と oneAPI/`icpx` 等を前提とする packaging 経路で読む。AOT 指定の可否や compiler/tool prerequisites は別途検査される（`build_sycl_linux.sh:1-18,20-38,49-55`）。値自体は package build ID のみに渡る（同:71-78）。
- Linux HIP script は `VARIANT` と ROCm build environment を必要とする。`COMMIT=unknown` の場合は commit 由来の `BUILD_ID` を書かず、package build ID には `unknown+rocm` が使われる（`build_hip_linux.sh:21-31,48-50,131-136`）。
- HIP の `VISION_ONLY` 経路は engine build と package 作成を省くが、`COMMIT` fallback と tarball checkout に対する `BUILD_ID` 書き込み判定はその分岐より前に実行される（`build_hip_linux.sh:31,48-50,60,85`）。
- `SHAPE` は ARM64 CUDA / SYCL / HIP の package shape 選択を変えるが、各 script にある `COMMIT` の読み取り・判定規則は変えない（`build_cuda_linux_aarch64.sh:29-31`, `build_sycl_linux.sh:41,70-75`, `build_hip_linux.sh:59-60,127,134-136`）。

## 実行時の詳細

ここでの「実行時」は packaging script の実行を指す。ARM64 CUDA script は環境値（空なら git HEAD）を確定し、`export COMMIT=$commit` で `engine/spark/build_engine.sh` と後続コマンドへ渡した後、`release-<version>-cuda13-<cuda>-aarch64-<先頭12文字>` を作って `package_engine.py --build-id` に渡す（`build_cuda_linux_aarch64.sh:24-41`）。

Windows CUDA の `source_commit(src)` は環境値をまず確認し、空の場合だけ git の HEAD を取得して検証する。返された値は engine build 後の `BUILD.json` で 12 文字に切られ、package build ID にも同じ 12 文字が使われる（`build_cuda_windows.py:135-142,167-168,186-196`）。

SYCL は build 成功後に `COMMIT` または fallback 値を決め、build ID として packer に渡す。HIP は script 冒頭で値を固定し、checkout に `.git` がなく `BUILD_ID` もまだない場合にのみ先頭 9 文字を `BUILD_ID` に書く。すでに `BUILD_ID` がある場合は `COMMIT` からの上書きはしない。続いて値を status 行・`BUILD.json`・package build ID に使う（`build_sycl_linux.sh:49-55,71-75`, `build_hip_linux.sh:31,48-57,86-90,131-136`）。

これらは packaging 用のプロセス起動時環境値であり、Strata server の request ごとに読む設定ではない。確認した script 内では子プロセスに環境全体が通常継承されるか、ARM64 のように明示 export される。実行中に親環境を書き換えて再評価する経路はない。

## ログと測定値

環境値の未指定・不正に対して明示エラーを出すのは ARM64 CUDA の git fallback も空だった場合（標準エラー、exit 2）と Windows CUDA の commit が規定形式でない場合（`fail()` が `SystemExit` を出す）である（`build_cuda_linux_aarch64.sh:26-28`, `build_cuda_windows.py:135-142,48-49`）。SYCL は git fallback に失敗すると `unknown` を build ID に含め、HIP は `unknown` を status と metadata に記録する。これらの値について専用の警告・失敗分岐はない（`build_sycl_linux.sh:54,74-75`, `build_hip_linux.sh:31,57,89,135`）。測定値は該当しない。

## 根拠

- `tools/packaging/build_cuda_linux_aarch64.sh:20-28,34-42`
- `tools/packaging/build_cuda_windows.py:135-142,151-177,186-196`
- `tools/packaging/build_sycl_linux.sh:18-38,49-55,71-80`
- `tools/packaging/build_hip_linux.sh:21-32,48-60,85-90,127-136`
