# `HIP_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部HIPランタイムの環境変数解釈は対象外。

## 役割

Strata が AMD/HIP エンジンおよび画像エンコーダーの子プロセスに渡す GPU 選択値です。serve の設定に `gpu` がある場合、HIP の番号で選んだ GPU をこの変数に設定します。複数 GPU の場合はカンマ区切りで順序も渡します。環境変数そのものの値を HIP ランタイムがどう解釈するかは、外部ライブラリの動作なのでここでは説明しません。

Strata の C++ エンジンは通常、この変数を読み取って値を検証するのではなく、`--gpu` 引数があるときに起動直後、GPU API の呼び出しより前に HIP ビルドではこの変数を設定します。HIP ビルドでは `CUDA_VISIBLE_DEVICES` ではなく `HIP_VISIBLE_DEVICES` を使うことがコードに明記されています。

## 値と優先順位

Strata が生成する値は、serve 設定から得た GPU 番号を10進表記し、複数なら `,` で連結した文字列です。Strata は `HIP_VISIBLE_DEVICES` の文字列自体を parse したり、範囲を検証したりしません。

| 状況 | 子プロセスに渡す値 |
|---|---|
| serve 設定の `backend` が `hip` で、`gpu` が1つ以上ある | `hip_visible(cfg)` の番号をカンマ区切りで設定。設定の `env` に同名キーがあれば、その値が後から優先 |
| `backend` が `hip` だが `gpu` がない | 親プロセスの環境を引き継ぐ。設定の `env` に同名キーがあればその値で上書き |
| HIP 以外で `gpu` がある | serve はこの変数を変更しない。親環境の値があれば引き継がれる |
| `vision.cuda_device` が設定されている HIP 構成 | 画像エンコーダー用の環境コピーで値をその番号1つに上書き |
| エンジン引数に `--gpu LIST` がある | C++ エンジンが既存値より優先して `LIST` を設定 |

serve の `gpu` 番号は設定・引数由来です。`hip_ordinal` があり、空白除去後に整数へ変換でき、GPU数が1以下なら、その番号が `gpu` より優先されます。変換できない `hip_ordinal` は無視して通常の GPU リストに戻ります。複数 GPU のリストは条件により `ordered_gpus()` が並べ替えることがあります（自動 layer split で速度を測定でき、カード差がある場合など）。

## 有効になる条件

- serve の上書きは、設定 `backend` が文字列 `hip` のときだけ行います。子環境は `os.environ` のコピーから始まるため、設定で上書きしない限り親プロセスの値は保持されます。
- HIP 構成で `gpu` が指定されていなければ、serve はこの値から GPU を推定・選択しません。親環境の値がそのまま渡ります。
- エンジン引数の `--gpu LIST` は、serve の子環境を作った後でもエンジン内でこの変数を上書きします。既存値が空でなく、`LIST` と異なる場合は stderr に `warning: --gpu ... overrides HIP_VISIBLE_DEVICES=... from the environment` を出します。
- `--gpu` の上書き処理は `STRATA_USE_HIP` または `STRATA_HIP_GFX906` のビルドで HIP 名を選びます。通常の CUDA ビルドでは `CUDA_VISIBLE_DEVICES` が対象です。
- エンジンが複数 GPU を見て、そのうちコンパイル対象外の GPU や未対応の wave size を検出すると、デバイス検査経路は stderr にエラー理由を出します。該当 GPU を隠す方法として `HIP_VISIBLE_DEVICES` を案内する箇所があります。実際にどのデバイスが見えるかはHIPランタイム側の処理です。

## 実行時の詳細

serve の `child_env()` は親環境を複製し、HIP GPU 選択を設定し、その後で config の `env` 項目を文字列化して適用します。この環境はエンジンの `subprocess.Popen` に渡され、通常のロード、lazy load 後の起動、エンジン再起動に使われます。複数レプリカ起動では各レプリカの設定から同様に子環境を作ります。

Windows では setup が `strata-device --list-devices` の結果を調べ、統合 Radeon が先に列挙される構成などで選択 GPU のHIP番号を `hip_ordinal` として記録します。serve はその番号を優先してエンジン環境を作ります。Linux では setup の KFD 順と HIP の順が対応するものとして、設定の `gpu` 番号を使います。Strata の `docs/AMD_HIP.md` も、デバイス選択に `ROCR_VISIBLE_DEVICES` / `HIP_VISIBLE_DEVICES` を利用できること、および選択番号がHIPの列挙順であることを説明しています。

画像エンコーダーは通常エンジンと同じ環境を受け取ります。config の `vision.cuda_device` があれば、そのプロセス専用に環境を複製して HIP の場合はこの変数を指定番号だけに置き換えます。エンジン用の GPU 選択と画像エンコーダー用の選択を別にできます。

プロセス環境は子プロセス起動時に渡されます。serve は起動後に親環境の変更を監視して再評価しません。エンジンの `--gpu` による上書きは、`main()` の引数走査で最初に見つかった `--gpu` とその次の引数を用い、GPU初期化前に行われます。

## 根拠

- `serve/server.py:2502-2515` — `hip_visible()`。Windows 用 `hip_ordinal` の優先条件、整数変換失敗時の fallback。
- `serve/server.py:2622-2639` — 親環境の複製、HIP用GPU番号の設定、config `env` による上書き、子環境の返却。
- `serve/server.py:2683-2696, 6378-6393` — 画像エンコーダー環境の複製と `vision.cuda_device` による選択。
- `serve/server.py:617-652, 697-699, 6422-6426` — 環境をエンジン起動情報として保持し、`Popen` に渡す箇所。
- `serve/server.py:2308-2315, 2587-2619` — 設定GPUの整数化と複数カードの順序決定。
- `src/program/generate.cpp:1803-1824` — `--gpu` による起動時の環境上書き、警告、HIP/CUDAごとの変数選択。
- `src/core/device.cu:51-62` — HIPエンジンが対応しないGPUを検出した場合の案内。
- `setup.py:2320-2345, 2418-2444` — HIPデバイス番号の取得とWindowsでの選択番号対応。
- `docs/AMD_HIP.md:81-84, 166-168` — setupによるHIP番号の使用と、HIPデバイスを選ぶ環境変数についての説明。
