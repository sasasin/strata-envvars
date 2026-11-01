# `DS4_DBG_CMP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。未コミット変更はありません。外部ライブラリの環境変数動作は対象外です。

## 役割

Metal 版 DS4 の embedding kernel が成功した後、出力バッファ `h` を CPU 側から走査し、要素数・NaN 数・ゼロ数と一部の値を stderr に出す診断用スイッチです。embedding の計算方法や値を変える分岐ではありません。

この読み取りは `metal/src/engine/ds4_host.cpp` に一箇所だけあります。`src/dsv41/ds4_kernels.cu` の `embed()` から呼ばれる `embed_addr()` が、`STRATA_METAL` 定義時だけ呼び出されます。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 診断ログを出さない |
| 空文字を含む、何らかの値が設定済み | 診断ログを出す |

実装は `std::getenv("DS4_DBG_CMP")` の null / 非 null だけを調べます。文字列・数値の parse、値域検査、無効値時の fallback はありません。したがって `0` や `false` も設定されていれば有効です。既定値は無効（未設定）です。CLI 引数や別の環境変数による上書きはありません。

## 有効になる条件

- macOS 向け Metal build であること。`metal/CMakeLists.txt` は Apple 以外で configure を失敗させ、Metal C++ headers がない場合は device runtime / engine の build をそこで終了します。
- DS4 の `strata_ds4` target を使うこと。この target は `STRATA_METAL=1` でコンパイルされます。通常の CUDA / HIP / SYCL 経路にはこの読み取り箇所はありません。
- DS4 の `embed()` が `embed_addr()` に到達し、Metal library が利用可能で、`ds4_embed_j` kernel の pipeline 取得と dispatch が成功すること。library が無効（`lib < 0`）の場合または pipeline 取得に失敗した場合、`embed_addr()` は false を返し、呼び出し元は別の embedding 実装へ進むため、この診断箇所には到達しません。
- 上記の条件に加えて、`DS4_DBG_CMP` が設定されていること。

サーバーモードや特定の CLI オプションを要求する判定はありません。読み取りはモデルの embedding 処理が呼ばれるたびに行われます。

## 実行時の詳細

`embed_addr()` は DS4 engine の stream を同期し、`ds4_embed_j` を shared Metal context に dispatch した後、`flush_runs()` を実行します。その後に環境変数を読み、設定されていれば `strata::gpu::host_view(h)` を得て `T * hc * dim` 個の float を調べます。`!(v == v)` を満たす要素数を `nonfinite` として数え、`v == 0.0f` を満たす要素数を `zeros` として数えます。前者の判定は NaN を数えるもので、正負の infinity は含みません。ゼロ判定は正負ゼロのどちらも数えます。

stderr への出力は次の二行です（書式は実装上の文字列）。

```text
DBG cmp: after embed n=... nonfinite=... zeros=...
DBG cmp: view ... ... ... | h=... h+1=...
```

二行目は `hv[0..2]` と `hv[dim * hc]`, `hv[dim * hc + 1]` を `%g` 形式で出します。`hv` が null の場合に `-1` を出す条件式もありますが、その前の集計ループは null を検査せず `hv[i]` を読みます。通常の有効なバッファ host view を前提としたコードです。

環境値は static 変数などへ保存されず、各 `embed_addr()` 呼び出しの dispatch 後に読み直されます。プロセス実行中の環境変更の反映は、環境変更後に行われる呼び出しで再判定される形です。`flush_runs()` は環境変数の判定前に常に呼ばれます。フラグによって追加されるのは host 側の走査と stderr 出力です。

## 根拠

- `metal/src/engine/ds4_host.cpp:195-235`: stream 同期、library / pipeline の確認、Metal dispatch、flush、設定有無判定、host view の走査と二つの stderr ログ。
- `src/dsv41/ds4_kernels.cu:2186-2193`: DS4 `embed()` から Metal `embed_addr()` を呼び、false の場合に代替 embedding 経路へ進む順序。
- `metal/src/engine/msl/ds4_init.metal:2581-2586`: `ds4_embed_j` が `rows` から `h` を書く Metal kernel。
- `metal/src/gpu/runtime.cpp:433-437`: `host_view()` が管理対象 allocation に対する CPU view を返し、見つからない場合は null を返す実装。
- `metal/CMakeLists.txt:16-18,51-55,135-171`: Apple 限定、Metal C++ headers の条件、DS4 source / `strata_ds4` target、および `STRATA_METAL=1` 定義。

`docs/DETAILS.md` および Strata の関連文書を検索しましたが、この変数の動作や測定値を裏付ける記述は見つかりませんでした。上記は調査対象 commit のソースコードに基づく説明です。
