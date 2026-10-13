# `STRATA_EXPERIMENTAL_SM60`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

セットアッププログラムが、Pascal（compute capability 6.x）と Volta（7.0）の NVIDIA GPU を利用可能な候補として扱うための opt-in です。対象変数を読むのは `setup.py` で、C++ エンジンや CUDA runtime がこの環境変数を読む箇所はありません。環境変数による許可が選択につながると、そのGPU世代向けに CUDA 12 の別エンジンを使います。実行ファイル内の旧世代GPU用コードと最低対応 compute capability は、環境変数ではなく CMake オプション `-DSTRATA_EXPERIMENTAL_SM60=ON` によってビルド時に決まります。

## 値と判定

`setup.py` は `os.environ.get("STRATA_EXPERIMENTAL_SM60", "").strip() == "1"` で文字列全体を比較します。空白を除いた値が厳密に `1` のときだけ、この変数による opt-in になります。

| 環境変数の状態 | この変数による opt-in |
|---|---|
| 未設定 | なし（空文字を既定値として比較） |
| 空文字、空白だけ | なし |
| `1`、` 1 ` | あり（前後の空白を除いた値が `1`） |
| `0`、`true`、`01`、`1x`、`-1` | なし（厳密一致しない） |

大文字小文字の変換や数値変換はしません。設定値が `1` 以外でもエラーにはならず、この変数からの許可がないものとして処理します。別経路で同じGPUが選択可能になることはあります。

## 有効になる条件

- 対象GPUは NVIDIA compute capability 6.0〜7.0（Pascal / Volta）です。`sm60_card()` は arch 値が 60 以上 70 以下かを判定します。CC 7.5 以上のGPUに対して、この値がGPUの選択や CUDA toolkit を強制するわけではありません。
- セットアップのGPU一覧や利用可否判定では、`experimental_sm60()` が真なら該当する旧世代GPUを許可します。ただし `--gpu` / `--gpus` 等による選択、モデルのGPU構成、VRAM条件など他の判定は別に適用されます。
- 旧世代GPUがモデルの実行GPUとして選ばれると、モデル単位で最も古いGPUの arch に基づき `cuda_choice()` が CUDA 12 を選びます。`--cuda 12|13` はこの選択を上書きします。`--cuda 13` で旧GPUを選ぶと、CUDA 13 エンジンにはその GPU 向けコードがなく実行できない旨をセットアップが警告します。
- この環境変数は、`--cuda 12`、Pascal / Volta GPUを明示的に選択すること、または利用可能な新しい NVIDIA GPU や対応 AMD GPU がないことによる自動選択の代わりにもなります。これらは `old_gpus_opt_in()` の独立した許可経路です。新しい NVIDIA GPU がある環境で本変数を設定しただけでは、旧GPUを自動で優先選択するのではなく、旧GPUを候補に加えます。
- HIP backend の場合、旧 NVIDIA GPU の警告は出さず、AMD側の経路になります。

## 実行時の詳細

セットアップ起動中に `old_gpus_opt_in()` が変数を読み、許可理由を `OLD_GPUS` に設定します。未設定を含め、値の判定はセットアップ処理の都度行われます。インストール済みモデルの起動経路でもこの helper が呼ばれます。環境変数自体はモデルの設定ファイルへ保存されません。CUDA engine の選択は `cuda_choice()` の結果をモデル設定に保存し、以降の起動でそのモデルが CUDA 12 engine を使う選択は維持されます。

環境変数が有効で、HIP backend ではない場合、セットアップは標準出力に次の警告を出します（`warn()` は標準出力に `[!]` を付けて表示します）。

```text
older NVIDIA GPUs (Pascal / Volta) can be used (STRATA_EXPERIMENTAL_SM60=1): experimental, through a second engine built with CUDA 12 (docs/OLDER_GPUS.md)
```

セットアップでソースビルドする場合、CUDA 12 engine は `engine-cuda12/` と専用 build directory を使い、`engine_defs()` は対象 GPU の arch が 75 未満、または toolkit が 12 の場合に `-DSTRATA_EXPERIMENTAL_SM60=ON` を CMake に渡します。Windows の既成 CUDA 12 engine を取得する経路もあります。したがって、環境変数が `1` であるだけで実行中のエンジンに旧GPU用コードが追加されることはありません。

CMake では、CUDA build でこのオプションが有効なとき、sm_60 より古いアーキテクチャは拒否し、コンパイル対象コードへ `STRATA_EXPERIMENTAL_SM60=1` を定義します。CUDA runtime のデバイス確認では最低 CC を通常の 7.5 から 6.0 に下げます。Volta向け attention や Pascal向け経路などもこの compile definition の有無で切り替わります。これらはビルドオプションの作用であり、実行時の環境変数を engine が直接解釈した結果ではありません。

## ログと資料との照合

`docs/OLDER_GPUS.md` は本変数を「旧世代GPUを利用可能として扱う」手段に挙げ、旧GPU使用時には CUDA 12 engine を選ぶこと、さらに `-DSTRATA_EXPERIMENTAL_SM60=ON` がビルド時に必要なことを説明しています。これは `setup.py` の候補判定・CUDA選択・ビルド引数、および CMake と device check の実装に一致します。同資料にはコミュニティ環境の測定値もありますが、この環境変数単独の性能や正確性を示す測定とはみなせないため、本調査では性能値を記載しません。

## 根拠

- `setup.py:925-953` — 環境変数の strip 後の厳密比較、GPU世代、他の旧GPU opt-in 理由。
- `setup.py:994-1003,1016-1021` — GPU利用可否と一覧表示。
- `setup.py:966-981,4991-5003,5075-5095` — CUDA 12/13 の決定、起動時の警告とドライバー条件。
- `setup.py:3381-3423` — エンジンの保存先、CUDA 12 の専用ビルド、CMake引数。
- `CMakeLists.txt:142-192,292-299` — CMakeオプション、対応 arch 下限、compile definition。
- `src/core/device.cu:281-313` — CUDA engine の実行時 CC 下限と未対応GPU時のエラー。
- `src/prefill/gemm.cu:471-490,609-642`, `src/kernels/cuda/qsa_prompt_attn.cu:741-743,1120-1126` — 実験ビルドで切り替わるCUDAコード経路の例。
- `docs/OLDER_GPUS.md:34-59,87-100` — CUDA 12 engine と opt-in の説明、ビルドオプションの説明。
