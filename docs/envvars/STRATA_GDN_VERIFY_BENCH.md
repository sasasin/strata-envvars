# `STRATA_GDN_VERIFY_BENCH`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は SYCL 版 `gdn_parity` の GDN verify-window 検査に、出力ベクトルと状態ベクトルの署名表示、および一部ケースの GDN kernel 計測を追加する。通常の GDN 推論経路を切り替える設定ではない。参照は `sycl/src/kernels/gdn_parity.cpp` の検査ループ内だけで、`strata` 実行ファイルや CUDA 側の同名相当処理からの読み取りは確認できなかった（`sycl/src/kernels/gdn_parity.cpp:922-959`）。

## 値と判定

`std::getenv` の戻り値が null かどうかだけを見る。文字列の parse、数値変換、内容比較はなく、変数が設定されていれば空文字も含めて有効となる。値の範囲・境界値・大文字小文字・前後空白による差はない（`sycl/src/kernels/gdn_parity.cpp:922`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL `gdn_parity` の通常実行経路 | 追加処理なし | `1`、`true`、`0`、`0anything`、空文字 | なし（環境変数が設定済みなら値にかかわらず有効） |

## 有効になる条件

- `sycl/CMakeLists.txt` の `STRATA_SYCL_PARITY` が ON で `gdn_parity` がビルドされていること。同オプションの既定値は ON で、OFF の場合このパリティ実行ファイル群を構成しない（`sycl/CMakeLists.txt:309-312`, `343-352`）。
- 実行が `--prefill-only` でないこと。このオプションは prefill 検査後に `main` を戻し、後続の GDN verify-window ループに入りません（`sycl/src/kernels/gdn_parity.cpp:213-229`, `235-242`）。
- 値を解釈する CLI 引数や、優先順位を持つ別の環境変数はない。`--selftest` は最終的な成功表示を選ぶ引数であり、この読み取りを無効化しない（`sycl/src/kernels/gdn_parity.cpp:213-229`, `982-985`）。

## 実行時の詳細

変数は、各 verify-window ケースの kernel 実行・参照計算・結果比較の後で読み取られる。関数内 static や起動時のキャッシュはなく、ケースごとに `std::getenv` を呼ぶ（`sycl/src/kernels/gdn_parity.cpp:873-922`）。

設定済みなら各ケースで `y` と `st` の float 値をビット列として走査し、FNV-1a 形式の 64-bit 値を計算して `GDNSIGNATURE` 行を標準出力に出す（`sycl/src/kernels/gdn_parity.cpp:922-933`）。この署名出力自体は比較結果や失敗判定を変更しません。パリティ不一致の判定は別に行われ、失敗数があれば最終的に終了コード 1 となります（`sycl/src/kernels/gdn_parity.cpp:905-920`, `982-985`）。

ベンチ計測は全ケースではなく、`n_keep < 0` かつ `tb == 0` の verify ケースに限られる。該当する T ごとに command graph へ `gdn_step_norm_multi` を32回記録し、graph を20回再生して最後の15回の計測値をソートし、中央の値を1呼び出しあたりのマイクロ秒として表示する（`sycl/src/kernels/gdn_parity.cpp:872-876`, `934-958`）。コマンドライン引数や別環境変数による値の上書き、子プロセスへの転送はこのコードにはない。

## ログと測定値

有効時の標準出力は次の形式。`GDNSIGNATURE` はケースごと、`GDNVERIFYBENCH` は上記の verify ケースごとに出る（`sycl/src/kernels/gdn_parity.cpp:932-958`）。

```text
GDNSIGNATURE T=<T> case=<case> y=<16桁16進数> state=<16桁16進数>
GDNVERIFYBENCH T=<T> us=<小数3桁>
```

`GDNVERIFYBENCH` の値は実行時に計測して出力する値であり、この調査では build や実行をしていないため、具体的な測定値は記載しない。変数未設定時には、これら2種類の行をこの分岐から出力しない。パリティ失敗の標準出力と終了コードは変数の設定にかかわらず別経路で発生する（`sycl/src/kernels/gdn_parity.cpp:916-920`, `982-985`）。

## 根拠

- `sycl/src/kernels/gdn_parity.cpp:213-242` — CLI 引数処理と `--prefill-only` の早期 return。
- `sycl/src/kernels/gdn_parity.cpp:873-922` — ケース構成、結果比較後の設定有無判定。
- `sycl/src/kernels/gdn_parity.cpp:922-959` — 署名計算・出力および条件付きベンチ計測。
- `sycl/src/kernels/gdn_parity.cpp:982-985` — パリティ失敗の終了コード。
- `sycl/CMakeLists.txt:309-312`, `343-352` — SYCL パリティターゲットのビルド条件と `gdn_parity` の登録。
