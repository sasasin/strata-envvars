# `STRATA_PF_OWN_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows 上の HIP サーバーで Strix Halo（gfx1151）の prompt path が自前バッファを使う設定になっているとき、起動時に `cudaMemGetInfo` が返す空き量を使って prompt chunk を事前に縮小する判定を復帰させる。既定では unified pool の空き量を実割当可能量と見なさず chunk を維持するが、この変数を有効にすると算術上の見積もりで chunk を小さくする。対象は `engine/src/program/generate.cpp` の `strata serve` 初期化経路に限られる（同ファイル: 13047-13097）。

## 値と判定

`std::getenv` の戻り値が非 null で、かつ値の先頭バイトが文字 `'1'` の場合だけ有効。文字列全体や数値としての妥当性は検査しない。したがって `1`、`10`、`1anything` は有効、未設定・空文字・`0`・`true`・先頭が空白の ` 1` は無効。大文字小文字の変換もない。既定は無効（同ファイル: 13076-13078）。

| ビルド・実行条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 全ビルド共通の読み取り判定 | 無効 | 先頭文字が `1`（例: `1`, `10`, `1abc`） | 空文字、`0`, `true`, ` 1` |

## 有効になる条件

- 値が有効でも、`o.prefill_own_keep_chunk` が true の場合に限り縮小判定へ影響する。このフラグは `STRATA_USE_HIP` ビルドで、Windows (`_WIN32`)、可視 GPU がすべて同一アーキテクチャの integrated GPU、かつ device 0 のアーキテクチャが gfx1151 のときに設定される（同ファイル: 4287-4303, 4399-4405）。
- その gfx1151 設定は `STRATA_PREFILL_BORROW=1` で prompt borrowing が選ばれる場合、または `STRATA_GFX1151_DEFAULTS=0` の場合には適用されない（同ファイル: 4399-4405）。
- `--prefill` などで決まった chunk が `own_fits` の算術チェックに通る場合、値の有無による差はない。判定は借用していない prompt path のバッファ見積もりと `cudaMemGetInfo` の空き量、headroom を比較する（同ファイル: 13049-13067, 13078-13097）。
- CUDA、Metal、Linux HIP、他の GPU 構成、または `o.prefill_own_keep_chunk` が false の経路では、値を設定してもこの分岐の動作は変わらない。CLI 引数がこの環境変数を上書きする処理はない。CLI は先に `o.prefill_chunk` を決め、その値が後段の算術チェックに使われる（同ファイル: 4000-4031, 13077-13097）。

## 実行時の詳細

環境変数は該当サーバー初期化経路で関数内 `static const bool` として初回評価され、以降はプロセス内でキャッシュされる。起動後に環境を変更しても再評価されない（同ファイル: 13076-13078）。

prompt path 初期化の前に `own_fits` が各自前バッファの必要量に 512 MiB（chunk が 512 以下なら 128 MiB）の headroom を加え、各対象 GPU の報告空き容量と比較する。gfx1151 の保持設定が立ち、かつこの変数が無効なら、算術チェックが失敗しても現在の chunk を維持し、「kept」の理由ログを出す。有効なら通常の縮小判定を行い、`6144, 4096, 3072, 2048, 1536, 1024, 512` の順で現在値より小さく、算術上 fit する最初の chunk を選ぶ。選んだ場合は `o.prefill_chunk` を更新する（同ファイル: 13047-13097）。

これは実割当を保証する判定ではない。候補が一つも fit しない場合はこの段階で chunk を縮小せず、そのまま prompt path を初期化する。その後、初期化が「do not fit」を返した場合は別の再試行ループが次の小さい chunk を試す（同ファイル: 13101-13140）。

## ログと測定値

保持設定が適用され、算術チェックが失敗し、変数が無効の場合は stderr に次の形式で出る（値は実行時の chunk と MiB 数）。

```text
strata serve: a <chunk>-token chunk's prompt buffers need <MiB> MiB, <MiB> MiB are reported free: kept (this GPU's memory is the unified pool; STRATA_PF_OWN_CHECK=1 steps the chunk down by that figure)
```

変数が有効で縮小候補が見つかると、stderr に `strata serve: a ... chunk's prompt buffers need ... MiB on CUDA..., ... MiB free: ...-token chunks` の形式で出て chunk を変更する。fit する場合、または縮小候補がない場合、この分岐からは上記のログは出ない（同ファイル: 13079-13097）。実割当失敗時には別途 `trying a ...-token chunk`、最終失敗時にはエラーと状況に応じた案内が stderr に出る（同ファイル: 13101-13140）。この変数自体についての測定値は記載されていない。

## 根拠

- `engine/src/program/generate.cpp:4287-4303, 4399-4405` — HIP/Windows/GPU 条件と保持設定を立てる条件。
- `engine/src/program/generate.cpp:13047-13078` — headroom、算術判定、変数読み取りとキャッシュ、保持分岐。
- `engine/src/program/generate.cpp:13079-13140` — chunk 縮小、初期化後の再試行、失敗時のログと終了。
- `engine/src/program/generate.cpp:4000-4031` — CLI `--prefill` による元の chunk 決定。
