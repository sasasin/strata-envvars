# `--resident-budget-gib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（engine root parser） |
| オプション | `--resident-budget-gib` |
| 別名 | なし |
| 値 | `N`: 0 より大きい GiB 数（小数可） |

## 役割

GPU expert cache に載らない expert のうち、expert profile で上位にランクされたものを、指定した GiB 予算まで起動時に RAM へコピーして保持します。予算に入らない expert は pack 内のファイルから読みます。engine parser はこの指定により mmap expert source と CPU resident copy を有効にします（`src/program/generate.cpp:546-549,2767-2776`）。

## 使い方

```sh
strata generate --pack /path/to/model-pack --tokens "1,2,3" --expert-profile /path/to/profile --resident-budget-gib 40
```

`--tokens` はこの build の必須入力で、profile を指定しない場合は resident CPU expert 設定の validation で失敗します（`src/program/generate.cpp:3044-3046,3174-3179`）。

## 値と既定値

- 省略時の内部値は 0 で、予算付き resident mode は有効になりません（`src/program/generate.cpp:549`）。
- 指定値は `std::atof` で double に変換し、`N > 0` を確認してから `N × 1,073,741,824` を byte 数へ変換します。byte 数への変換時に整数へ切り捨てられます（`src/program/generate.cpp:2767-2770`）。
- 0、負数、または `std::atof` が 0 を返す値は `N > 0` の判定を通らず、stderr に `strata generate: --resident-budget-gib needs N > 0` を出して終了コード 2 で返ります。値がない場合は共通の引数取得処理が `--resident-budget-gib needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420,2767-2770`）。
- 同じ option を複数回指定した場合、parser は各回の値を同じ field に代入するため、後に現れた値が残ります（`src/program/generate.cpp:2416-2421,2767-2776`）。

## 実行時の動作

- option を読むと `--mmap-experts` 相当の file source、`--resident-cpu-experts` 相当の RAM copy、page-locking を設定し、headroom を 4 GiB にします。`STRATA_RESIDENT_PIN=0` は page-locking を無効にし、`STRATA_RESIDENT_HEADROOM_GIB` が 0 以上の数値なら headroom をその値に置き換えます（`src/program/generate.cpp:2767-2776`）。
- RAM に入れる対象は GPU cache にない expert の補集合です。profile の順位に従って、各 expert の blob が予算内に収まるものを選び、残りはファイルから供給します。prompt path が cache slot を借りる構成では、budget に余裕がある限り借用領域の expert も同じ上限内で保持対象になります（`src/core/expert_source.cpp:3516-3518,3544-3564,3565-3584,3669-3675`）。
- 実際のコピーは expert source の起動時初期化で行われ、成功時は resident RAM 量、page-locked / locked / pageable の状態、GPU cache の resident 数などを stderr に出力します（`src/program/generate.cpp:8203-8205,8249-8270`）。
- option は `--mmap-experts` と併用する前提の設定を自動で行います。このため `--shared-expert-arena` とは併用できず、両方を指定すると parser 後の validation が stderr にエラーを出して終了コード 2 を返します（`src/program/generate.cpp:2771-2772,3040-3042`）。明示的な `--expert-profile` も必要です（`src/program/generate.cpp:3044-3046`）。
- Windows では RAM のほか commit capacity も上限判定に使われます。要求値が available RAM / commit capacity の小さい方から headroom と 256 MiB margin を引いた容量を超える場合、予算はその容量へ clamp され、stderr に調整メッセージが出ます（`src/core/expert_source.cpp:94-100,3516-3542`）。
- budget が指定されると file tier の unbuffered 読み込みを source に設定し、起動時に unbuffered または file cache 経由のどちらになったか stderr に出します（`src/program/generate.cpp:5725-5739`）。budget なしの場合は `STRATA_UNBUFFERED_LOAD` があってもこの分岐では無視される旨が表示されます（同:5728-5739）。
- `setup.py` にも同名 option がありますが、そちらは索引の `source-setup/root` に属する別 parser です。ここでは索引上の `strata-engine/root` に対応する `src/program/generate.cpp` の動作だけを記載しています（`docs/cli/README.md:1268-1271,1507-1510`）。

## 適用条件と副作用

- file-backed expert source が開けない場合、source のエラーを stderr に出して推論開始前に終了します（`src/program/generate.cpp:5709-5721`）。
- 予算を clamp しても RAM copy を確保できないなど、resident copy が作れない場合は警告を出し、GPU が保持しない expert を model files から読む mmap 経路へフォールバックします。これは予算付き経路では終了ではなく警告として扱われます（`src/program/generate.cpp:8275-8284`）。利用可能メモリを取得できない場合や、確保・page-locking の問題の詳細は `FileExpertSource` の失敗理由として伝播します（`src/core/expert_source.cpp:3516-3523,3722-3732,3785-3813`）。
- 起動時に RAM を確保し、page-locking が可能な場合は pinned memory を使います。driver が page-locking を拒否すると pageable memory を試します（`src/core/expert_source.cpp:3722-3726,3785-3813`）。要求値は利用可能 RAM / commit capacity に応じて小さくされ得るため、指定した GiB 数そのものが常に保持されるわけではありません（同:3524-3542）。
- budget 付きでも RAM に入らない expert はモデルファイルから読むため、そのファイル読み込みが続きます。source は実際の RAM copy 後にも unbuffered 読み込み選択を再確認し、Windows / Linux では変更があれば stderr に示します（`src/program/generate.cpp:8286-8306`）。

## 出力とエラー

主な parser エラーは値の検証時に stderr と終了コード 2 で報告されます（`src/program/generate.cpp:2418-2420,2767-2770`）。起動時には、RAM budget、profile 順に保持した expert 数、ファイル tier の読み込み方式が stderr に出ます（`src/core/expert_source.cpp:3538-3542,3562-3564`; `src/program/generate.cpp:5731-5739`）。予算付き resident copy に失敗した場合の警告と mmap fallback は上記「適用条件と副作用」を参照してください（`src/program/generate.cpp:8275-8284`）。

## 根拠

- engine root parser、内部既定値、値変換、resident mode の設定: `src/program/generate.cpp:546-549,2416-2421,2767-2776`
- 適用前の source / profile 条件、mmap source の初期化: `src/program/generate.cpp:5707-5724,3040-3046`
- memory clamp、profile 順での予算配分、prompt lend region の配分: `src/core/expert_source.cpp:94-100,3516-3564,3565-3584,3669-3675`
- 成功・失敗時の処理、読み込み方式、fallback: `src/program/generate.cpp:5725-5739,8203-8219,8249-8306`
- 対象スコープと索引: `docs/cli/README.md:1134-1142,1268-1271,1507-1510`
- 利用者向け説明の照合資料: `docs/DETAILS.md:322-339`。性能値は特定機材・条件での記録であり、本書では一般的な性能保証として扱っていません。
