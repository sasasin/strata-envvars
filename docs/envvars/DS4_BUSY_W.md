# `DS4_BUSY_W`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `main...origin/main` で未コミット変更なし。

## 役割

Metal 上の DSV41 runtime が CPU 側 expert 処理中に別の Metal queue で走らせる busy-spin kernel の幅を指定します。値は 256-thread threadgroup の数として使われ、実際の dispatch thread 数は `256 * width` です。Strata のコード上、この設定は GPU busy dispatch の幅を調整します。性能向上の程度はこの調査では測定していません。

## 値と判定

`metal/src/mtl_rt.mm:273` で `std::getenv("DS4_BUSY_W")` を調べ、設定されていれば `std::atoi()` の結果を `std::max(1, ...)` で下限 1 にして `uint32_t` に変換します。未設定なら既定値は 1 です。

| 値 | `width` |
|---|---:|
| 未設定 | 1 |
| 空文字 | 1（`atoi` が 0 を返し、下限 1 が適用される） |
| 正の整数 | その整数 |
| 整数に変換できない文字列、または 0 | 1 |
| 負の整数 | 1（下限 1 が適用される） |
| 数字の後ろに文字が続く値 | `atoi` が読み取った数字部分を使用。例: `3extra` は 3 |

文字列全体の厳密な検証や上限 clamp はありません。`atoi` が整数を読み取れない場合は 0 となり、1 に補正されます。大きな正数を指定した場合も明示的な上限検査はなく、値は dispatch thread 数の計算に使われます。

## 有効になる条件

- `DS4_BUSY_W` の読み取り箇所は `metal/src/mtl_rt.mm` の DSV41 busy runtime です。CMake はこのファイルを `ds4_rt_mm` としてコンパイルし、`STRATA_DS4_RUNTIME=1` を定義しています。同じ Metal build では `strata_ds4` に `STRATA_METAL=1` を定義します（`metal/CMakeLists.txt:151-169`）。したがって通常の CUDA/HIP backend や Metal 上の他 target に一般適用される設定ではありません。
- `DS4_BUSY_W` は `ds4_busy_begin()` が busy kernel を dispatch するところまで進んだ場合にだけ幅へ反映されます。通常の DSV41 経路では、layer に CPU 側で処理する expert があり `ents` が空でないときに `ds4_busy_begin()` が呼ばれ、CPU expert 処理後に `ds4_busy_end()` が呼ばれます（`src/dsv41/ds4_model.cu:10555-10565`）。
- `DS4_BUSY_ALL` が設定されていると、Metal build の `forward()` の開始時にも busy 処理を開始し、終了時に終了処理を呼びます（同 `src/dsv41/ds4_model.cu:9693-9700`）。この経路は `ents` の有無にかかわらず呼び出されます。
- 別環境変数 `DS4_BUSY` が文字列全体で `"0"` の場合、`ds4_busy_begin()` は即時 return するため、busy kernel は開始せず、`DS4_BUSY_W` は dispatch に使われません。`DS4_BUSY` の値判定結果は関数内 static 変数に保存されます（`metal/src/mtl_rt.mm:235-238`）。
- 初回初期化に失敗した場合、または busy dispatch がすでに走っている場合は `ds4_busy_begin()` が return し、幅を読みません（同 `metal/src/mtl_rt.mm:239-266`）。

## 実行時の詳細

`DS4_BUSY_W` は `ds4_busy_begin()` 内の関数ローカル `static const` として初期化されます。したがって環境値は、初期化が成功し、`DS4_BUSY=0` による早期 return もなく、最初に dispatch を行う経路に到達した時に評価されます。その後はプロセス内で値がキャッシュされ、実行中に環境を変更しても幅は再評価されません（`metal/src/mtl_rt.mm:235-273`）。

初回の busy 開始では Metal device、kernel pipeline、command queue、共有 flag buffer を初期化します。準備ができると、幅に応じた thread 数で busy-spin kernel を二つ目の queue に投入し、command buffer を commit します。`ds4_busy_end()` は共有 flag を 1 にして spin を終わらせ、running 状態を解除します（`metal/src/mtl_rt.mm:239-289`）。

`DS4_BUSY_W` 自体について、Strata は警告・ログを出しません。busy runtime の初期化失敗時も、この経路では `NSError` の内容を表示せず、`g_busy.ok` が false のまま開始処理を終了します（`metal/src/mtl_rt.mm:257-266`）。幅に関する別の明示的なエラー・終了処理も見当たりません。実際の dispatch が受理される範囲や GPU の性能状態は、このコード調査からは断定できません。

## 根拠

- 値の取得、整数変換、下限 1、未設定時の幅 1、および dispatch サイズ: `metal/src/mtl_rt.mm:270-279`
- 初回初期化、失敗時・実行中の早期 return、busy kernel の投入と終了 flag: `metal/src/mtl_rt.mm:235-289`
- DSV41 target の `STRATA_DS4_RUNTIME` / `STRATA_METAL` build 定義: `metal/CMakeLists.txt:151-169`
- CPU expert 処理に伴う begin/end 呼び出し: `src/dsv41/ds4_model.cu:10555-10565`
- `DS4_BUSY_ALL` による forward 全体を囲む呼び出し: `src/dsv41/ds4_model.cu:9693-9700`
