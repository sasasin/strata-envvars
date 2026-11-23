# `STRATA_VIT_Q8_EXPAND`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP 版の Strata own vision tower が、mmproj の Q8_0 行列を GPU に置く際、圧縮された Q8_0 のまま保持する経路を無効にして、読込時に F16 へ展開する環境スイッチである。既定では圧縮形式を保持し、積の直前に共有 scratch buffer へ F16 化する。展開を選ぶと行列ごとに F16 の重みを保持する。F32、F16、BF16 行列や画像の出力形式を切り替える変数ではない（`terminal/tools/vision/own/vit_gpu.cu:466-467, 741-767, 781-787`）。

実際に読むのは CUDA/HIP 共通実装 `VitGpu::load` である。own vision tower の GPU backend を含むビルドで、`strata-vision --gpu`（server の `"vision": {"gpu": true}` も同じ reader 起動経路）を使う場合にだけ到達する。値は reader プロセスのモデル読込時に取得される（`terminal/tools/vision/own/vit_gpu.cu:917-954`; `terminal/tools/vision/own/own_reader.cpp:63-77`; `terminal/tools/vision/strata_vision.cpp:67-70`; `terminal/serve/server.py:3017-3026, 3114-3121`）。

## 値と判定

`std::getenv` で設定有無を調べ、設定されていれば `std::atoi(e) != 0` を代入する。unset では `VitGpuImpl::q8_expand` の初期値 `false` のまま。空文字、数値に変換できない文字列、`0`、`-0`、`0anything` は 0 となり無効。`1`、`-1`、`+1`、`1anything` など、`atoi` が先頭部分から非ゼロ整数に変換する値は有効になる。整数の後ろは検査されず、大文字小文字や `true`/`false` といった語としての真偽値判定もない。前置空白と符号は `atoi` の変換規則に従う。`atoi` が `int` の範囲を超える入力の結果はこのコードでは規定されないため、使用可能な境界値として扱えない（`terminal/tools/vision/own/vit_gpu.cu:466, 952-954`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA または HIP の own GPU tower | `false`（Q8_0 を compact 保持） | `1`, `-1`, `1anything`（非ゼロ整数に変換） | 空文字, `0`, `-0`, `0anything`, `true`, `abc` |
| CPU、SYCL、Metal の reader | この名前を読まない | 該当なし | 該当なし |

CLI 引数や設定ファイルとの優先順位はない。GPU reader の `load` 時の環境変数だけで決まり、サーバー設定の `--gpu` は GPU 経路を選択するが、この値を上書きしない。server は reader 起動に `vision_env` の環境辞書を渡し、通常はエンジン環境をそのまま使う。CUDA/HIP デバイスを別指定した場合も変更されるのは可視デバイス等であり、この変数の判定規則は変わらない（`terminal/serve/server.py:3997-4012, 8906-8907`; `terminal/serve/server.py:3114-3121`）。

## 有効になる条件

- own vision tower の GPU reader がビルドされていること。CUDA は `STRATA_VISION_CUDA` または standalone の `STRATA_VIT_OWN_CUDA`、HIP は `STRATA_VISION_HIP` または `STRATA_VIT_OWN_HIP` により共通の `vit_gpu.cu` が組み込まれる（`terminal/tools/vision/own/CMakeLists.txt:13-22, 24-44, 120-131`）。
- `strata-vision` を `--gpu` 付きで実行すること。GPU reader を使わない CPU 経路では `STRATA_VIT_Q8_EXPAND` を参照しない（`terminal/tools/vision/strata_vision.cpp:67-70`; `terminal/tools/vision/own/own_reader.cpp:63-89`）。
- mmproj に Q8_0 の行列があること。Q8_0 以外の行列にはこの分岐の影響がない。Q8_0 でもテンソル要素数が 32 の倍数でない、または raw byte 数が `(要素数 / 32) * 34` と一致しない場合は compact 分岐に入らず、通常の変換側へ進む（`terminal/tools/vision/own/vit_gpu.cu:711-716, 741-763`）。
- SYCL と Metal は別ファイルの GPU 実装を使い、Q8_0 を読込時に F16 へ変換するが、この環境変数を読み取らない。これらの backend で設定しても Strata の分岐は変わらない（`terminal/tools/vision/own/CMakeLists.txt:140-163`; SYCL: `terminal/tools/vision/own/vit_sycl.cpp:331-355`; Metal: `terminal/tools/vision/own/vit_metal.mm:160-180`）。

## 実行時の詳細

`VitGpu::load` は tower geometry の検査後、行列アップロード前に環境値を一度読み、`m.q8_expand` に保存する。各行列の読込で Q8_0 かつ compact 条件を満たし、`q8_expand == false` なら、34 byte/32 要素の raw Q8_0 を GPU にコピーし、最大行列サイズに応じた共有 F16 scratch の大きさを記録する。読込後にその scratch を一度確保し、GEMM ごとに必要な Q8_0 行列を scratch に F16 dequantize してから積を計算する（`terminal/tools/vision/own/vit_gpu.cu:741-752, 781-787, 1012`）。

`q8_expand == true` なら compact 分岐を飛ばし、`gg.read_f32` で Q8_0 を float 値に読み出し、各値を F16 に変換してその行列の重み領域として GPU に保持する。この経路では compact Q8_0 用の shared scratch は必要にならない（`terminal/tools/vision/own/vit_gpu.cu:753-767, 1012`）。設定は `load` ごとに取得されるため、ロード後にプロセス環境を変えても既にロード済みの tower には反映されない。server が reader を再起動した場合は新しいプロセスの load で再評価される（`terminal/tools/vision/own/vit_gpu.cu:917-954`; `terminal/serve/server.py:2963-2973, 3114-3121`）。

CLI による優先上書きはなく、空文字も「未設定」扱いではなく `atoi("") == 0` により明示的に無効になる。GPU reader の起動や load に失敗した場合、reader は `ERR ...` を stdout に出して非ゼロ終了する。例えば GPU 重みの割当失敗は `GPU memory: <CUDA/HIP runtime error>` を load error にし、reader 側は `cannot load the vision encoder <mmproj> (<error>)` を返す。server は GPU reader が起動しない場合、利用可能なら CPU reader へ fallback する（`terminal/tools/vision/own/vit_gpu.cu:693-700`; `terminal/tools/vision/own/own_reader.cpp:45-49, 76`; `terminal/serve/server.py:2967-2972, 3042-3045`）。

## ログと測定値

この変数自体について、有効・無効を示す専用ログはない。GPU 読込成功時には通常の `strata-vision: own tower (...) loaded ... on the GPU` が stderr に出るが、Q8_0 の保持形式は表示しない（`terminal/tools/vision/own/own_reader.cpp:93-94`）。失敗時は上記の `ERR ...` が stdout に出て、GPU reader は load error の戻り値 1 で終了する。独立の測定値は対象資料に見当たらない。`docs/DETAILS.md:1139` は Q8_0 mmproj の一般的なサイズと CPU 利用の推奨を説明しているが、この環境変数の GPU 展開切替や比較測定は述べていない。

## 根拠

- 候補名の Strata ソース内参照は `terminal/tools/vision/own/vit_gpu.cu:466, 953`。466 行はメンバーのコメント、953 行が唯一の実環境読み取りである。
- 値の読取、default、および CUDA/HIP 共通の位置: `terminal/tools/vision/own/vit_gpu.cu:454-468, 917-954`。
- Q8_0 の compact / expand 処理、GEMM 時の dequantization とエラー: `terminal/tools/vision/own/vit_gpu.cu:711-787`。
- scratch 確保・GPU 割当エラー: `terminal/tools/vision/own/vit_gpu.cu:693-700, 1012`。
- build backend の違い: `terminal/tools/vision/own/CMakeLists.txt:120-163`; SYCL `terminal/tools/vision/own/vit_sycl.cpp:331-355`; Metal `terminal/tools/vision/own/vit_metal.mm:160-180`。
- reader の GPU 条件、load 失敗出力と成功ログ: `terminal/tools/vision/own/own_reader.cpp:45-49, 63-94`; CLI `terminal/tools/vision/strata_vision.cpp:67-70`。
- server の引数・環境引き渡しと再起動経路: `terminal/serve/server.py:2963-2973, 3017-3029, 3114-3121, 3997-4012, 8906-8907`。
- 関連資料との照合: `docs/DETAILS.md:1133-1144`。
