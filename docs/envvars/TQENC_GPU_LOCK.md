# `TQENC_GPU_LOCK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 同梱の trellis エンコーダー `tools/tqenc.py` が GPU encode を行う間、共有ロック `/data/gpu.lock` と指定カード用ロック `~/locks/gpu<N>.lock` を取得するための変数です。Strata 本体の推論 engine やサーバー設定ではなく、同梱の Python エンコードツール向けです。GPU encode は `tqenc.encode(..., gpu=True)` のときだけ選択され、HIP ライブラリ `tqh_encode` を呼びます（`tools/tqenc.py:137-164`）。

## 値と判定

| 環境変数の状態 | 挙動 |
|---|---|
| 未設定 | `os.environ.get()` が `None` を返し、ロックを取らずに `self.ok=True` で続行 |
| 設定あり | 値を変換・検証せずカード番号文字列として `~/locks/gpu%s.lock` のパスに埋め込み、ロック取得を試みる |
| 空文字 | 未設定ではないため有効。パスは `~/locks/gpu.lock` になる |

数値 parse、範囲制限、空白除去、大文字小文字の処理はありません。たとえば `TQENC_GPU_LOCK=2` は `~/locks/gpu2.lock` を使います。設定値が存在するかだけが分岐条件です（`tools/tqenc.py:76-90`）。

## 有効になる条件

- 呼び出し側が GPU encode を要求すること。`gpu=False` ならこの変数は参照されません。trellis `pilot.py` と `build_swap.py` / `proxy_ldl.py` は `--gpu` を受け取り（`tools/trellis/pilot.py:153,200,214`、`tools/trellis/build_swap.py:88,127-130`、`tools/trellis/proxy_ldl.py:38,69-73`）、DSV41 converter は `--cpu` がない場合 GPU encode を要求します（`tools/dsv41/tq_convert.py:77-78,138-140`）。
- `gpu=True` でも `exact` が真、または型が `TQ2_T` ならロック処理前に `ValueError` になります（`tools/tqenc.py:154-157`）。
- ロックを使う経路は `fcntl` を import し、`flock` でファイルロックを行うため、Unix 系の実行環境を前提にしています（`tools/tqenc.py:76-104`）。コード上の OS 判定や Windows 用代替処理はありません。

`TQENC_GPU_LOCK` が設定されてロック経路に入る場合、待ちの上限は別変数 `TQENC_GPU_WAIT` で決まります。これは `float()` で変換され、未設定時は `1e9` 秒です。文字列が float として不正なら `ValueError` が伝播します。負数・0 を含め値の範囲検査はありません（`tools/tqenc.py:76-103`）。

## 実行時の詳細

変数は `_gpu_lock.__enter__()` のたびに読み取られ、値を static cache しません。各 GPU encode 呼び出しのたびに、まず `~/locks/EXCL_WAIT` の有無を確認し、存在中は 2 秒間隔で待ちます。その後 `/data/gpu.lock` を共有ロック、カード別ファイルを排他ロックとして、どちらも非ブロッキング取得を 0.2 秒間隔で再試行します。取得した file descriptor は `__exit__()` で逆順に close されます（`tools/tqenc.py:76-110,157-164`）。

`EXCL_WAIT` 待機または flock 待機が `TQENC_GPU_WAIT` を超えると `self.ok=False` になり、GPU 呼び出しを行わず CPU encoder に切り替えます。CPU encoder の thread 数は `TQENC_CPU_THREADS` があればその `int()` 値、なければ `threads` 引数が真ならその値、いずれも偽なら 24 です（`tools/tqenc.py:91-103,157-164`）。タイムアウト時にこの helper 自身が出すログや例外はなく、呼び出し元は通常の encode 結果を受け取ります。ファイルを開けない等の OS エラーや `fcntl` の import 失敗は捕捉されず、encode 呼び出し元へ伝播します（同 `:80-104`）。

値の更新は次の GPU encode 呼び出しから反映されます。すでにロック待ち中の呼び出しは、その `__enter__()` で読み込んだカード値と wait 値で継続します。CLI の `--gpu` / `--cpu` が GPU encode を選ぶかを決め、この環境変数はその選択を上書きしません。

## 根拠

- 実際の環境読み取り、ロック対象パス、待機と timeout 処理、release: `tools/tqenc.py:67-110`
- GPU/CPU の分岐、GPU での HIP encoder 呼び出し、timeout 後の CPU fallback: `tools/tqenc.py:137-165`
- 同梱 CLI から GPU encode を選ぶ例: `tools/trellis/pilot.py:153,200,214`; `tools/trellis/build_swap.py:88,127-130`; `tools/trellis/proxy_ldl.py:38,69-73`; `tools/dsv41/tq_convert.py:77-78,138-140`
- 候補一覧には記載があります: `docs/envvars/000_envvers.md:1677`。
