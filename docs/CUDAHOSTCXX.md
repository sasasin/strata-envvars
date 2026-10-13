# `CUDAHOSTCXX`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

`setup.py` がローカルのCUDAエンジンまたはCUDA画像エンコーダーをCMakeで構成するときに、CUDAコンパイルで使うホストC++コンパイラを指定します。Strataの通常実行時にエンジンが読む変数ではありません。

設定値は `-DCMAKE_CUDA_HOST_COMPILER=...` としてCMakeのconfigure引数に渡されます。`CUDAHOSTCXX` が空または空白だけなら、`CXX` の値を代わりに渡します。`CC` はCコンパイラ用、`CXX` は通常のC++コンパイラ用として別々に渡されます。

## 値と判定

`host_compiler_defs()` は `os.environ.get(..., "").strip()` で取得します。値をパスとして検証・正規化したり、実行可能ファイルの存在を確認したりはしません。

| `CUDAHOSTCXX` | `CXX` | `cuda=True` の場合に渡すCUDAホストコンパイラ定義 |
|---|---|---|
| 未設定、空文字、空白だけ | 空でない | `-DCMAKE_CUDA_HOST_COMPILER=<CXX>` |
| 未設定、空文字、空白だけ | 未設定、空文字、空白だけ | 定義を渡さない。選択はCMake側に委ねる |
| 空白除去後に値がある | 任意 | `-DCMAKE_CUDA_HOST_COMPILER=<CUDAHOSTCXX>` |

前後の空白は取り除かれますが、値の大文字小文字や内部の空白はそのままです。値の妥当性確認はこの関数では行わず、コンパイラとして使えるかは後続のCMake構成・ビルド段階で決まります。コロンやカンマ等を使った複数候補形式もこのコードでは解釈しません。

## 有効になる条件

- CUDAエンジンのローカルビルドでは `host_compiler_defs(True)` が呼ばれ、値があればCMake定義に含まれます。
- GPU版の画像エンコーダーをローカルビルドするときも `host_compiler_defs(True)` が呼ばれます。
- CPU版画像エンコーダーのビルドでは `host_compiler_defs(False)` のため、`CUDAHOSTCXX` は渡されません。`CXX` が設定されていれば通常のC++コンパイラ定義だけが渡されます。
- HIPエンジンのビルド経路ではこのhelperを呼ばず、`CUDAHOSTCXX` は使用されません。HIP経路に続くCPU画像エンコーダーにも渡されません。
- ビルド済みエンジンと必要な画像エンコーダーが有効と判断され、`build_engine()` が再コンパイルせずに戻る場合、この変数はその実行ではCMakeに渡されません。コンパイラ選択だけを理由に再ビルドする判定は `build_engine()` にありません。

## 実行時の詳細

値は `host_compiler_defs()` の呼び出しごとに読み取られ、関数内でキャッシュされません。setupプロセス起動後にPythonの `os.environ` が変更されてから関数を呼べば、その時点の値が対象になります。Strataサーバーや生成リクエストのたびに読む処理はありません。

CMakeの引数を作る順序は `CC`、`CXX`、`CUDAHOSTCXX` です。CUDAホストコンパイラの値は、明示された `CUDAHOSTCXX` があればそれを使い、なければ空白を除去した `CXX` を使います。`CUDAHOSTCXX` の値があっても、`cuda=False` ならCUDAホストコンパイラ定義自体は加えません。`cmake_build()` はこれらの定義を含めて `cmake -S ... -B ...` を実行します。Windowsでは生成したバッチファイルから同じconfigure引数を実行します。

既存のCMakeビルドディレクトリにもcompiler定義をconfigure引数として渡す設計ですが、setupがビルドをスキップした場合にはconfigure自体が走りません。CMakeが既に構成済みのディレクトリで指定変更をどう扱うかはCMake側の挙動であり、ここではStrataの動作として断定しません。

## 根拠

- `setup.py:3338-3349` — 環境変数の読み取り、`.strip()`、`CUDAHOSTCXX` から `CXX` へのfallback、`cuda` 条件、CMake定義の生成。
- `setup.py:3289-3312` — 定義リストをconfigure引数に加えてCMakeを実行する処理。Windowsでは同じ引数でバッチファイルを実行。
- `setup.py:3402-3407,3418-3433` — エンジン/画像エンコーダーの再ビルド判定と、CUDAビルド・GPU画像エンコーダー・CPU画像エンコーダーそれぞれでhelperを呼ぶ条件。
- `setup.py:2647-2678` — HIPエンジンと、そのCPU画像エンコーダーのビルド経路。`host_compiler_defs()` は呼び出されない。
- `docs/TROUBLESHOOTING.md:52-59` — CUDAツールキットとホストコンパイラの組み合わせに関するsetup利用者向け案内。具体的な変数処理の根拠は上記実装。
