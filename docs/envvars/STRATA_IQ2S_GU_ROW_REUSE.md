# `STRATA_IQ2S_GU_ROW_REUSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の grouped expert gate/up 計算で、IQ2_S（内部形式 `TG == 22`）の重みを処理するときに、Battlemage 系 GPU 上で 2 行分の入力再利用カーネルを選ぶかを制御する。再利用カーネルは `launch_gu_row_reuse<22>` を起動し、通常の lane kernel への切替点より先に判定される。環境変数は計算結果の値を指定するものではなく、カーネル選択を切り替える。実装は `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5895-5908`、呼び出し元の format dispatch は同ファイル `6020-6067`、grouped expert の gate/up dispatch は同ファイル `7767-7774, 7874-7883`。

## 値と判定

`strata::bm_default_on` が `std::getenv(name)` で読み、文字列全体を parse せず先頭文字だけを見る。値が未設定または空文字なら Battlemage 判定に従い、非空なら先頭文字が `0` のとき false、それ以外は true。したがって `0`, `0anything`, `00`, `false` はそれぞれ false, false, false, true となる。`1`, `true`, `off`, ` 0`, `-1` は true。空白除去、数値変換、大文字小文字変換はしない。根拠: `engine/sycl/include/strata/sycl_queue.hpp:193-200`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL grouped gate/up の `TG == 22`, `LN == 8` で `STRATA_GRID_SLM == 0`。GPU が Battlemage と判定される場合 | 有効 | `1`, `true`, `off`, ` 0`, `-1` | `0`, `0anything`, `00`, 空文字（unset と同じく既定判定） |
| 同じ経路で GPU が Battlemage 以外と判定される場合 | 無効 | 非空で先頭が `1` 以外の文字（helper の値は true になる） | `0` 始まり、または空文字（既定 false） |

非空値の先頭文字が `0` 以外でも、後段に Battlemage の実行時条件があるため、他 GPU 上ではこのカーネルは選ばれない。Battlemage 判定は SYCL device のアーキテクチャ情報やデバイス名等から行われ、Xe3 もその判定に含まれる。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5897-5900`、`engine/sycl/include/strata/sycl_queue.hpp:154-191`。

## 有効になる条件

- Strata の SYCL backend で、この `iq_kernels.dp.cpp` の native grouped expert 経路が使われ、gate/up 型が IQ2_S（`L.gu_type == 22`）であること。grouped expert は空の group/entry 数なら早期 return する。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7767-7774, 7874-7877`。
- `launch_gu_port` のインスタンスが `TG == 22`, `LN == 8` であること。`launch_gu_lanes` は `STRATA_GU_LANES` に従って lane 数を選ぶ（有効値 4/8/16/32、既定 `kExpertLanes`）。この変数の再利用分岐は 8 lane 専用である。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4481-4487, 5895-5900, 5940-5949`。
- ビルド時に `STRATA_GRID_SLM` が 0 であること。分岐は `#if !STRATA_GRID_SLM` の範囲にあり、同ファイルの既定値は 0。1 にしてビルドした場合、この環境変数を読むコード自体がコンパイル対象から外れる。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:484-489, 5895-5910`。
- `g_old_kernels` と `g_split_multi` がともに false であること。どちらかが true なら再利用分岐を通らず、後続の通常経路で処理される。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5897-5908, 6053-6067`。
- `STRATA_EXPERT_ROW_E3` は再利用カーネルに入った後の 3-entry variant 選択に関係する。未設定・空文字では `bm_default_on(..., false)` により既定 off、非空値は先頭が `0` 以外なら on。再利用カーネルの選択そのものの条件ではない。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4437-4458`、`engine/sycl/include/strata/sycl_queue.hpp:196-200`。

## 実行時の詳細

環境変数を CLI 引数や設定ファイルで上書きする Strata の処理はこの経路にはなく、helper がプロセス環境を直接読み取る。読み取りは `launch_gu_port` の該当テンプレート経路に初めて到達したときに行われ、`static const bool reuse` に保存されるため、同じ関数テンプレート実体では以後再読込されない。プロセス実行中に環境を変更しても判定は更新されない。static はデバイスごとではなくテンプレート実体ごとの値で、最初の初期化時に渡された device が unset/空文字時の既定判定に使われる。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5895-5900`、`engine/sycl/include/strata/sycl_queue.hpp:196-200`。

条件を満たす場合、stderr に `strata: IQ2_S raw two-row GU reuse enabled (8 lanes, SIMD16)` を一度出して `launch_gu_row_reuse<22>` を呼び、通常の `native_gu_kernel` への到達前に return する。E3 variant が選ばれれば、同じ起動関数内で別途 `strata: IQ2_S exact three-entry row reuse enabled` を出す。変数が false、Battlemage でない、旧カーネル/分割経路、または `STRATA_GRID_SLM` が有効なビルドの場合は、この専用起動・専用ログはなく、後続の通常 kernel 経路を使う。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4437-4458, 5895-5918`。

## ログと測定値

この変数について Strata の資料に条件付きで記載された性能測定値は確認できなかった。実行時の有効ログは前節の stderr 文言で、条件を満たさない場合に理由ログを出す処理はこの分岐にはない。grouped gate/up の起動後は `check("native_expert_grouped/gu")` を通るが、変数固有の失敗メッセージや終了処理は確認できなかった。根拠: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5897-5908, 7883`。

## 根拠

- `engine/sycl/include/strata/sycl_queue.hpp:154-200` — GPU 世代判定と環境変数の値判定。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:484-489` — `STRATA_GRID_SLM` の既定値。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4437-4458` — row reuse 起動と E3 variant。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5843-5918` — IQ2_S row reuse の条件、ログ、起動先、通常経路。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5940-5949, 6020-6067` — lane dispatch と `launch_gu` の実行経路。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7767-7774, 7874-7883` — grouped expert の entry 条件と gate/up format dispatch。
- `docs/INTEL.md:589-599` — Battlemage 上の runtime control 既定値に関する資料。実装の判定はソースコードを根拠とした。
