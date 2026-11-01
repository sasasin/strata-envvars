# `STRATA_ENGINE_NICE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の Python サーバーが engine 子プロセスを起動するとき、その子プロセスに `os.nice()` で加える nice 値を指定します。対象は `StrataEngine` 経由で起動する engine です。サーバー通常起動のほか、replica と split serving も同じ `StrataEngine` を使います。engine の CLI 引数や engine 自身の環境設定を変更する変数ではありません。

Linux で変数が未指定または空白だけの場合、KFD topology から検出した GPU のいずれかが内蔵 Radeon の対象 architecture なら nice increment 5、それ以外なら 0 です。対象 architecture は `gfx1035`, `gfx1036`, `gfx1037`, `gfx1103`, `gfx1150`, `gfx1151`, `gfx1152`, `gfx90c` です。

## 値と判定

| 状況 | `engine_nice()` の結果 |
|---|---:|
| `sys.platform` が `linux` で始まらない | `0`。環境変数も GPU topology も調べない |
| Linux、未設定または空文字・空白のみ | 対象 architecture の GPU が一つ以上あれば `5`、それ以外は `0` |
| Linux、整数として変換できる値 | `0`〜`19` に clamp した値 |
| Linux、空白を除去しても整数にできない値（例: `x`, `3.0`） | `0`。GPU による既定値へは戻らない |

値は `str(asked).strip()` の後 Python の `int()` で変換されます。符号付き整数も受け付け、負値は 0、19 より大きい値は 19 になります。空白だけは変数未指定と同じ自動判定です。値が `0` なら内蔵 GPU の自動既定値を明示的に無効化します。

helper の引数 `env` が空でない辞書ならそこから値を読みます。`env` が `None` または空辞書なら `os.environ` を参照する実装です。通常の engine 起動では helper に渡した環境辞書がそのまま子プロセスにも渡されます。CLI 引数にこの nice 値を指定する経路はありません。

## 有効になる条件

- `StrataEngine.__init__()` が `lazy=False` で engine を実際に起動する経路で評価されます。`lazy=True` では初期化早期に戻るため、その時点では環境変数を読みません。
- 自動値の判定は Linux のみです。Linux 以外では明示値も含め常に 0 です。
- Linux の自動値は、`/sys/class/kfd/kfd/topology/nodes` の GPU node `properties` から読み取る `gfx_target_version` と `simd_count` による architecture 検出に依存します。読み取り不能、値不正、対象 GPU なしの場合、architecture を得られず自動値は 0 です。
- 明示値が有効な整数なら、GPU topology に関係なくその値（0〜19）になります。明示値が無効なら 0 となり、自動判定を使いません。
- OS/backend/build macro/モデル状態による追加分岐はこの helper にはありません。これはサーバー側の子プロセス起動処理であり、engine の CLI 単独起動にはこの Python 処理は介在しません。

## 実行時の詳細

`StrataEngine` はログの開始記録後、engine 起動ごとに `engine_nice(env)` を呼びます。値が 0 なら `preexec_fn` に nice 処理を設定せず、優先度ログも出しません。非 0 なら既存の CPU affinity 設定がある場合は先に適用し、その後、子プロセス内で `os.nice(nice)` を実行します。サーバープロセス自身の nice 値は変更しません。engine は `[exe, "--serve", *args]` として起動され、指定された `env` を引き継ぎます。

非 0 のとき、サーバーの stdout に次の行を出します（実際の値に置換）。このログは明示値か自動値かを区別しません。

```text
[strata] engine priority: nice +N (this PC has built-in Radeon graphics that usually draw the desktop; STRATA_ENGINE_NICE=0 turns it off)
```

読み取りは engine 起動のたびに行われ、helper 内に cache はありません。環境辞書を使う起動では、その辞書の値が評価と子プロセスへの引き渡しの双方に使われます。起動後に値を変えても、すでに動いている engine の nice 値は再設定されません。再起動では再評価されます。子プロセス生成時の OS エラーは `StrataEngine` から再送出されます。生成後に engine が `READY` を返さず timeout または早期終了した場合は `EngineDied` になる起動失敗処理がありますが、コードから `STRATA_ENGINE_NICE` 固有の engine 終了経路は確認できません。

## 根拠

- 候補名の本番読み取りと判定: `serve/server.py:3458-3472`。Linux 判定、環境取得、空文字処理、`int()` 変換、clamp、無効値時の 0、および topology による既定値を実装しています。
- 内蔵 GPU architecture の取得と対象一覧: `serve/server.py:3475-3491,3571`。KFD topology の `properties` を読み、architecture を組み立てます。
- 読み取り時期、nice 適用、ログ、子プロセス起動と環境引き渡し: `serve/server.py:1043-1045,1064-1079`。
- 通常サーバー、replica、split serving からの `StrataEngine` 起動: `serve/server.py:8688-8711,8757-8777,9273-9279`。
- 起動エラーの再送出と、engine が `READY` を返さない場合の失敗処理: `serve/server.py:1080-1084,1085-1153`。
- 設計説明との照合: `docs/STRIX_HALO.md:246-247` は Linux の内蔵 Radeon 搭載機で nice +5、`STRATA_ENGINE_NICE=0` による無効化と別値指定を説明しています。値の変換詳細は同資料にはなく、上記コードを根拠としました。
