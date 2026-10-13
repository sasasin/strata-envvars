# `STRATA_RESIDENT_PIN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--resident-experts` または `--resident-budget-gib N` で作る CPU resident expert copy を、GPU が直接 DMA できる page-locked memory として確保するかを選びます。既定は page-locked です。値が厳密に `0` なら通常の pageable memory に切り替えます。通常の `--resident-cpu-experts` 単独指定ではこの環境変数は読み取られず、resident copy の確保処理にも入りません。

対象コードには CUDA/HIP 共通の `src/program/generate.cpp` と SYCL 用の `sycl/src/program/generate.cpp` があり、どちらも同じ値判定と option 設定をしています。

## 値と判定

環境変数を読むのは `--resident-experts` と `--resident-budget-gib` の引数処理中です。まず両 option が `resident_pin = true` にし、その後、値が存在し文字列全体がちょうど `"0"` の場合だけ `false` に戻します。

| 環境変数の状態 | `resident_pin` |
|---|---:|
| 未設定 | 有効（`true`） |
| `0` | 無効（`false`） |
| 空文字、`00`、`false`、`1`、その他の文字列 | 有効（`true`） |

数値変換や先頭文字判定ではなく、`std::string(v) == "0"` による大文字小文字を区別する完全一致です。値はコマンドライン解析時に通常の `getenv` で読み、static cache はしていません。プロセス起動後に環境を変更しても、すでに設定された option は変わりません。

## 有効になる条件

- `--resident-experts` または `--resident-budget-gib N` のどちらかが指定されたときに限り、この変数の判定結果が使われます。
- `--resident-experts` は `--mmap-experts` と `--resident-cpu-experts` を有効にして resident mode を設定します。resident mode は mmap と静的 `--expert-profile` を必要とします。条件を満たさない場合は `--resident-cpu-experts requires --mmap-experts and a static --expert-profile` として終了します。
- `--resident-budget-gib N` は `N > 0` を要求し、同じく mmap と resident CPU experts を有効にします。resident copy 自体が利用可能 RAM / commit と headroom に収まらない場合は、環境変数の値にかかわらず予算経路の fallback があります。
- セットアップコードは HIP の resident 構成を作るとき、起動 config の `env` に `STRATA_RESIDENT_PIN=0` を設定します。これはエンジン既定値の変更ではなく、そのセットアップ経路が書く config 値です。

## 実行時の詳細

値が有効（unset を含む）なら、`FileExpertSource::pin_cache_complement()` に `pin=true` が渡ります。CUDA 実装は page-locked/mapped arena をまず確保し、失敗時は pageable allocation へ fallback します。Linux では page-lock が file cache の回収に依存する場合など、step 単位での登録に切り替わる経路もあります。従って `1` は page-lock の成功を保証しません。作成後のログで `mapped pinned`、`locked resident`、または `pageable` と実状態を確認できます。

値が厳密に `0` なら page-locked allocation/register の経路を選ばず、pageable resident memory を確保します。resident copy は引き続き作られますが、CUDA 実装のログ分類は `pageable resident` です。ソースコメントは、この場合 GPU へのコピーが CPU 経由になると説明しています。これは resident copy の配置方法だけの切り替えで、expert cache の選択や `--resident-budget-gib` の数値そのものは変更しません。

どちらの経路でも resident copy は GPU cache にない expert を起動時にファイルからコピーして構築し、その後の miss や適応 swap に使われます。メモリ不足などで whole resident mode が作れない場合、`--resident-experts` の soft 経路は警告を出して通常の mmap/file-cache 読み取りに戻ります。明示 budget の失敗時も warning を出し、GPU cache 外の expert をモデルファイルから読む経路になります。

## ログと資料

resident copy 確保時に `FileExpertSource: allocating ... page-locked cache complement` または `... pageable resident cache complement` が出ます。完了時のログは実際の状態を `mapped pinned`、`locked resident`、`pageable resident` のいずれかで示します。resident memory が作れない場合は `strata generate: WARNING: ...` の fallback 警告が出ます。

`docs/DETAILS.md` は `STRATA_RESIDENT_PIN=0` を mapped mode と同じ token を得る指定として記載し、`docs/TROUBLESHOOTING.md` は低 RAM 時に pageable にする回避策として説明しています。これらは資料上の説明で、ここでは性能値の主張はしていません。

## 根拠

- 引数ごとの既定 `true` と厳密な `"0"` 判定: `src/program/generate.cpp:2150-2170`, `sycl/src/program/generate.cpp:1958-1979`。
- resident CPU experts の前提条件、remote cache 制約: `src/program/generate.cpp:2350-2364`。
- resident copy 作成呼び出しと soft fallback: `src/program/generate.cpp:6720-6740,6792-6810,6848-6868`。
- CUDA allocation、pageable fallback とログ: `src/core/expert_source.cpp:2817-2825,2859-2905,3014-3023,3168-3179`。
- SYCL allocation の page-locked / pageable 分岐と最終ログ: `sycl/src/core/expert_source.cpp:1855-1863,1890-1900,2130-2146`。
- HIP resident 構成で config に `0` を書く処理: `setup.py:5738-5750`。
- docs との照合: `docs/DETAILS.md:183-188`, `docs/TROUBLESHOOTING.md:101-103`。
