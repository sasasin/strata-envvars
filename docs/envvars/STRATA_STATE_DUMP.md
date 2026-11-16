# `STRATA_STATE_DUMP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL verifier の診断用フックで、GDN 層の状態を生バイナリとしてファイルへ出力する。一般的なフラグ処理ではなく、`std::getenv` の戻り値が null かどうかだけを見る。出力は verifier の通常の計算・状態更新を切り替えず、状態の読み出しとファイル I/O を追加する。読み取り箇所は `sycl/src/core/verify.cpp` の `Verifier::run()` にだけある。CUDA/HIP など他 backend の Strata 所有コードにはこの名前の読み取り箇所がない（候補一覧の backend 表記は SYCL）。`docs/DETAILS.md` にこのフックの説明は見つからなかった。

ただし、この変数だけでは出力されない。`STRATA_STATE_HASH_FILE` も空でないパスに設定され、そのファイルを開けている必要がある。外側の条件を満たすと、状態ハッシュ記録に加えて本変数によるダンプ処理が行われる。`state_hash_file()` は `STRATA_STATE_HASH_FILE` を関数内 `static` に一度だけ読み、`fopen(path, "w")` の結果を保持する（`sycl/src/core/verify.cpp:174-183, 2308-2317`）。

## 値と判定

`Verifier::run()` の状態ハッシュ処理内で、各 GDN 状態について `std::getenv("STRATA_STATE_DUMP") != nullptr` を判定する（`sycl/src/core/verify.cpp:2308-2317`）。文字列の変換・比較はしない。

| 条件 | 未設定 | ダンプを有効にする値 | ダンプを有効にしない値 |
|---|---|---|---|
| SYCL verifier の `run()`。ただし `STRATA_STATE_HASH_FILE` が非空で、同変数用の出力ファイルを開けた場合 | 無効 | 空文字、`0`、`1`、`false`、その他すべての設定値 | なし（環境変数が存在すれば有効） |
| `STRATA_STATE_HASH_FILE` が未設定・空文字、またはそのファイルを開けない場合 | 無効 | なし。本変数の値にかかわらず外側の処理へ入らない | すべて |

空文字を含め、`STRATA_STATE_DUMP` が設定されていれば有効条件を通る。ただしダンプ対象はさらに `windows == 0` かつループ添字 `i < 4` に限られる。値の空白、大文字小文字、数値としての妥当性は調べない。`STRATA_STATE_HASH_FILE` のパスは `state_hash_file()` 初回呼び出し時に評価・キャッシュされ、空文字なら `nullptr` を保持する。対象変数 `STRATA_STATE_DUMP` は static cache されず、対象状態ごとに読み直される（同:174-183, 2315-2317）。

## 有効になる条件

- SYCL backend の `Verifier::run()` 経路を使うこと。対象名の実読み取りは `sycl/src/core/verify.cpp` に限られ、CUDA 側の `src/core/verify.cpp` などにはない（同:2278-2280, 2308-2317）。
- `STRATA_STATE_HASH_FILE` が非空のパスで、初回評価時に `fopen(path, "w")` が成功していること。ファイルを開けなければ `state_hash_file()` は null を返し、`STRATA_STATE_DUMP` は参照されない（同:174-183, 2308-2317）。
- 対象 `SessionState` に GDN 状態があり、`ss.gdn_alloc` のループ対象が存在すること。各状態のダンプは verifier のローカル `i` が0から3までに限定される。ファイル名に使う層番号は `ss.gdn_ord0 + i`（同:2310-2317）。
- 各 `Verifier` の `windows` が0の間だけダンプする。通常の `run()` は窓の完了時に `windows` を増やし、レイヤー分割の先行 stage も次 stage へ渡す前に増やすため、各 verifier が扱う最初の窓が対象となる（同:2818-2821, 2869-2871）。
- CLI 引数による上書きや、他の変数が `STRATA_STATE_DUMP` の値を変更する処理は確認できなかった。必要な別変数は `STRATA_STATE_HASH_FILE` のみ。

## 実行時の詳細

`Verifier::run()` は入力の staging 後に `state_hash_file()` を呼びます。戻り値が有効な場合、GPU queue を待ち、GDN 状態ごとに device memory から `hb` へ `gf * 4` バイトをコピーして完了を待ちます。`gf` は `ssm_state_size * ssm_v_heads * ssm_state_size + ssm_conv_channels * (ssm_d_conv - 1)` です。`STRATA_STATE_DUMP` が設定され、窓番号が0で、ローカル添字が4未満なら、`<値>_gdn<ss.gdn_ord0+i>.bin` を `wb` で開き、読み出した状態バイト列をそのまま書き込みます（`sycl/src/core/verify.cpp:2307-2319`）。

たとえば値が `/tmp/state` なら `/tmp/state_gdn0.bin` のようなファイル名になる。値が空文字でも設定済みと判定され、`_gdnN.bin` という相対ファイル名が使われる。`fopen` に失敗した場合はそのファイルを飛ばし、`fwrite` の戻り値も確認しないため、作成・書き込み失敗をこのコードは報告しない（同:2315-2318）。ファイルを開くモードは `wb` なので、同じパスが既にあれば切り詰める。複数の verifier が同じ層番号・パスへ書く構成での競合や結果は、このコードから保証されない。

## ログと測定値

`STRATA_STATE_DUMP` 自体を有効化したことや、ダンプファイルの成功・失敗を示すログはない。`STRATA_STATE_HASH_FILE` が有効なら同じ外側の処理で GDN/QSA のハッシュ行をそのファイルへ記録し、各 `run()` の処理末尾で flush するが、これは本変数がなくても行われる診断出力である（`sycl/src/core/verify.cpp:2319-2336`）。この機能に関する測定値は資料にない。

## 根拠

- 候補一覧の記載: `data/settings-register.json:39362-39373`（backend `sycl`、読み取り元 `sycl/src/core/verify.cpp:2315`）。
- `STRATA_STATE_HASH_FILE` の一度限りの評価とファイル open: `sycl/src/core/verify.cpp:174-183`。
- 状態のコピー、対象名の判定、ファイル名生成と書き込み: `sycl/src/core/verify.cpp:2307-2321`。
- verifier 窓番号の進行: `sycl/src/core/verify.cpp:2818-2821, 2869-2871`。
- ハッシュファイルへの記録と flush: `sycl/src/core/verify.cpp:2319-2336`。
