# `DS4_DBG_MOE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 エンジンの host-routed MoE 経路で、中間テンソルと MoE 出力を調べる診断フックです。Metal ビルドでこの変数が設定されていると、入力 `x`、shared expert の `sg` / `su`、SwiGLU 後の `sh`、MoE 合成後の `moe_out` / `sh_out` について NaN 数と最大絶対値を stderr に出します。また `s1` の形式情報、layer / token 数、VRAM 行数、CPU slot 数、CPU 部分出力の最大絶対値も出します。数値計算や routing を切り替える設定ではありません。

## 値と判定

| ビルド | 未設定 | 設定時 |
|---|---|---|
| `STRATA_METAL` 定義あり | 診断しない | 値を問わず診断する。空文字も有効 |
| `STRATA_METAL` 定義なし（CUDA / HIP 等） | 診断しない | 診断しない。helper が定数 `false` を返すため環境値を読まない |

文字列比較、数値変換、範囲検査はありません。Metal では `ds4_dbg()` が呼ばれるたびに `std::getenv(name) != nullptr` を評価します。判定を `static` に cache していないため、コード上は後続のチェック時にも再評価されます。CLI 引数、設定ファイル、別の環境変数による優先順位や fallback はありません。

## 有効になる条件

- `src/dsv41/ds4_launch.h` の `STRATA_METAL` 分岐がコンパイルされていること。Strata の Mac 向け DeepSeek-V4.1 設定はエンジンの `backend` を `metal` にします（`setup.py:8743-8756`）。
- モデル処理が `ds4_model.cu` の MoE host-routed 経路を通ること。この処理は tensor-parallel (`nm > 1`) をエラーにして戻った後の経路であり、先行する async mailbox 経路にはこの診断チェックがありません（`src/dsv41/ds4_model.cu:10301-10416`）。
- その経路で MoE 層が処理され、各診断条件に到達すること。

CUDA/HIP でも同じソースにチェック呼び出しはありますが、`ds4_dbg` は定数 `false` なので実行されません。Python の DeepSeek エンジン設定や GPU 選択がこの名前を設定する処理は見つかりませんでした。通常は起動元のプロセス環境が子プロセスへ渡されます。サーバーの `child_env()` は `os.environ` を基に子環境を作り、設定ファイルの `env` を重ねますが、この変数専用の上書きはありません（`serve/server.py:3747-3763`）。

## 実行時の詳細

`ds4_launch.h` は Metal では引数名を `getenv()` に渡す helper、その他のビルドでは常に false の helper を定義します（`src/dsv41/ds4_launch.h:30-37`）。Metal の host-routed MoE 経路では、shared expert の計算を enqueue した後に `x`、`sg`、`su` と `s1` の情報を出し、SwiGLU 後に `sh` を調べます。MoE 結果を合成した後は `h_part` の最大絶対値、`moe_out`、`sh_out` を調べます（`src/dsv41/ds4_model.cu:10421-10453,10582-10591`）。

`dbg_nf()` は Metal の deferred work を flush してから対象バッファを走査します。実装は `v == v` が偽の値だけを `nonfinite` として数えるため、このカウントは NaN の数です。infinity はカウントされず、`fabs(v) > mx` の比較を通って `max` を infinity にします。NaN の最初の index と最大値を、`DBG nf il=%d %s n=%zu nonfinite=%zu first=%zu max=%.4g` の形式で stderr に出します（`src/dsv41/ds4_model.cu:9759-9765`）。MoE 箇所にはさらに `DBG s1 fmt=...` と `DBG moe il=... T=... vram_rows=... cpu_slots=... max|h_part|=...` が出ます。これらの診断走査は追加の同期・CPU 処理を伴いますが、出力された数値に対する修正やエラー終了はこの変数の処理にはありません。

未設定、非 Metal ビルド、または該当経路を通らない場合、このフックによるログはありません。CLI / server の別による判定差や、環境変数値に応じた処理結果の fallback はありません。

## 根拠

- `src/dsv41/ds4_launch.h:30-37` — Metal の環境読み取りと、非 Metal の定数 false。
- `src/dsv41/ds4_model.cu:10301-10416` — async 経路と host-routed 経路、tensor-parallel の早期エラー。
- `src/dsv41/ds4_model.cu:10421-10453,10582-10591` — MoE 内の診断対象と実行位置。
- `src/dsv41/ds4_model.cu:9759-9765` — 非有限値の定義、走査、stderr の書式。
- `setup.py:8743-8756` — Mac 向け設定で `backend: metal` を指定。
- `serve/server.py:3747-3763` — server が継承環境を基にエンジンの子環境を作成。
