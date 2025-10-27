from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Any, List, Optional
from dev.services.comment_service import CommentService
from dev.model.models import CommentOut, CommentCreate, User
from dev.services.auth_service import get_current_user
from bson import ObjectId

router = APIRouter(
    prefix="/comments",        # main.py의 /api와 결합 -> /api/posts
    tags=["Comments"]
)

@router.get('/{post_id}', response_model=List[CommentOut])
async def get_comment_all(
    post_id: str,    
    sort: Optional[str] = Query(default='createdAt', description='정렬 필드'),
    page: int = Query(1, ge=1), 
    limit: int = Query(10, ge=1, le=100), 
    comment_service: CommentService = Depends(CommentService)):

    comments = await comment_service.comment_find_all(sort=sort, page=page, limit=limit, post_id=post_id)
    status_check(comments, status_code=404, message='게시물들을 찾을 수 없습니다.')
    
    return comments

@router.get('/count', response_model=int)
async def get_comments_count(comment_service: CommentService = Depends(CommentService)):
    return await comment_service.comment_count()

@router.get('/{post_id}/{comment_id}', response_model=CommentOut)
async def get_comment_detail(
    post_id: str,
    comment_id: str,
    comment_service: CommentService = Depends(CommentService)):

    status_check(ObjectId.is_valid(comment_id), status_code=400, message='유효하지 않은 댓글입니다.')
    status_check(ObjectId.is_valid(post_id), status_code=400, message='유효하지 않은 게시물입니다.')
    commnet = await comment_service.comment_find_one(comment_id=comment_id, post_id=post_id)
    status_check(commnet, status_code=404, message='게시글을 찾을 수 없습니다.')
    return commnet

@router.put('/{post_id}', response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_new_comment(
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    comment_service: CommentService = Depends(CommentService)):

    comment_data.parent_id = None if comment_data.parent_id is None else ObjectId(comment_data.parent_id)

    inserted_id = await comment_service.comment_insert(
        comment_data=comment_data, 
        auth_id=current_user.email,
        auth_name=current_user.username
    )

    created_comment = await comment_service.comment_find_one(comment_id=inserted_id, post_id=comment_data.post_id)
    status_check(created_comment, status_code=500, message='글 작성 실패')
    
    return created_comment

@router.delete('/{post_id}/{comment_id}', response_model=bool)
async def delete_comment(
    post_id: str,
    comment_id: str, 
    current_user: User = Depends(get_current_user),
    comment_service: CommentService = Depends(CommentService)):
    
    # 2. (검증) ID 형식이 올바른지 확인합니다.
    status_check(ObjectId.is_valid(post_id), status_code=400, message='유효하지 않은 게시물입니다.')
    status_check(ObjectId.is_valid(comment_id), status_code=400, message='유효하지 않은 댓글입니다.')

    # 3. 🔑 (인가) 삭제 전에 먼저 게시글을 조회합니다.
    comment = await comment_service.comment_find_one(comment_id=comment_id, post_id=post_id)
    
    status_check(comment, status_code=404, message='게시글을 찾을 수 없습니다.')
    status_check(comment['auth_id'] == current_user.email, status_code=403, message='삭제 권한이 없습니다.')

    deleted = await comment_service.comment_delete_one(comment_id=comment_id, post_id=post_id)
    
    status_check(deleted, status_code=500, message='삭제에 실패했습니다.')
    return deleted

@router.patch('/{post_id}/{comment_id}', response_model=CommentOut)
async def update_comment(
    comment_id: str, 
    new_comment: CommentCreate, 
    current_user: User = Depends(get_current_user),
    comment_service: CommentService = Depends(CommentService)):
     # 2. (검증) ID 형식이 올바른지 확인합니다.
    status_check(ObjectId.is_valid(comment_id), status_code=400, message='유효하지 않은 댓글입니다.')
    
    # 3. 🔑 (인가) 삭제 전에 먼저 게시글을 조회합니다.
    comment = await comment_service.comment_find_one(comment_id=comment_id, post_id=new_comment.post_id)
    
    status_check(comment, status_code=404, message='게시글을 찾을 수 없습니다.')
    status_check(comment['auth_id'] == current_user.email, status_code=403, message='삭제 권한이 없습니다.')

    updated_comment_id = await comment_service.comment_update_one(post_id=new_comment.post_id, comment_id=comment_id, comment_data=new_comment)

    status_check(comment, status_code=500, message='수정에 실패했습니다.')
    updated_comment = await comment_service.comment_find_one(comment_id = updated_comment_id, post_id=new_comment.post_id)

    return updated_comment


def status_check(post: Any, status_code: int, message: str):
    if not post:
        raise HTTPException(status_code=status_code, detail=message)
