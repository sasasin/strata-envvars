# `STRATA_VISION_ARCH_CHECK`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

HIP版の画像エンコーダー `strata-vision-hip` が、検出したAMD GPUのgfxアーキテクチャをビルド時の対応アーキテクチャ一覧と照合する起動時チェックを切り替えます。既定ではチェックし、ビルド対象に含まれないGPUを見つけると、カーネル処理を始める前にエラーを標準出力へ出して終了コード3で終了します。値を0にするとこの照合だけを省略します。通常利用者向けの画像設定ではなく、ソースにある開発・診断用フックです。

## 値と判定

`tools/vision/strata_vision.cpp` は `getenv()` の値を `std::atoi()` に渡し、その結果が0以外かで判定します。文字列全体の妥当性検査はありません。

| 環境変数の状態・値 | アーキテクチャ照合 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 無効（`atoi("")` は0） |
| `0`、`00`、`false`、整数として読めない文字列 | 無効（変換結果0） |
| `1`、`2`、`-1`、`1tail`、` 1` | 有効（変換結果が0以外） |

`atoi` は先頭の空白と符号を許し、整数として読める先頭部分を使います。たとえば `1tail` は1として扱われ、`tail1` は0になります。数値の範囲外の文字列に対する `atoi` の結果はこの実装から保証できないため、値として案内しません。

## 有効になる条件

この変数を読むのは、`STRATA_VISION_HIP` を定義してビルドした画像エンコーダーだけです。さらに実行時に `--gpu` が指定され、GPUデバイスが見つかったときにチェック分岐へ進みます。CPU版、CUDA版、Metal版、SYCL版、およびHIP版でも `--gpu` なしではこの変数による照合は行いません。

HIP版がGPUのデバイス行からgfx名を得られなかった場合は `g_gfx` が空のため、環境変数の値に関わらず照合を行いません。複数デバイスの情報が記録された場合、現在の分岐は先頭のgfx名だけを照合します。対応一覧はビルド時の `STRATA_VISION_HIP_ARCHS` です。

## 実行時の詳細

エンコーダーは llama backend を初期化し、その情報ログから `quiet_log()` がgfx名を抽出して `g_gfx` に保存します。HIP版で `--gpu` が有効なら、`STRATA_VISION_ARCH_CHECK` が未設定、または `atoi` の結果が非0で、かつ先頭の検出gfx名がビルド一覧にない場合、標準出力に次の行を出して終了コード3で終了します。

```text
ERR this GPU (<検出gfx名>) is not in the picture reader's build (<ビルド時一覧>)
```

0を指定すると、この「ビルド一覧にない」場合の事前終了を飛ばします。gfx一覧外のGPUで後続のカーネル処理を実行できることを保証するものではありません。`gpu_arch.h` のコメントは、対応外GPUでは最初のカーネルで失敗し得るため、通常は事前に拒否すると説明しています。

サーバーがHIP GPU readerの起動失敗を受け取ると、CPU readerが設定されている場合はCPUへ切り替え、`[strata] the GPU picture reader did not start (...); pictures are read on the CPU` を出します。このフォールバックは `serve/server.py` 側の動作です。

値は画像エンコーダーの各プロセス起動時に `main()` 内で読み取られます。サーバーはreaderを起動するとき `env` を `popen()` に渡します。プロセス起動後に親の環境を変更しても、起動済みエンコーダーがこの判定を再評価するコードはありません。readerが再起動されたときは、その起動プロセスに渡された環境で再び判定されます。

## 根拠

- `tools/vision/strata_vision.cpp:46-55` — backendのデバイスログからgfx名を取り出して保存。
- `tools/vision/strata_vision.cpp:141-173` — backend初期化、GPU有無の確認、環境変数の読み取り、既定ONの照合、エラー出力と終了コード3。
- `tools/vision/gpu_arch.h:13-32` — gfx名の抽出と、カンマ・セミコロン・空白区切りのビルド一覧との完全一致判定。
- `tools/vision/CMakeLists.txt:18-29,84-109` — HIP readerのビルド条件、対応アーキテクチャ一覧の指定と `STRATA_VISION_HIP` 定義。
- `serve/server.py:2542-2550,2584-2605` — readerの引数と環境の保持、GPU reader起動失敗時のCPU fallback、子プロセスへの環境引き渡し。
- `docs/DETAILS.md:1664-1672` — 画像readerの概要とAMD readerのCPU fallbackに関する説明。環境変数の既定値や値の判定は文書に記載されていない。
